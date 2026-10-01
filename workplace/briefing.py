"""Four compact chapters for a ten-minute executive demonstration.

The full analytical pages stay available. This view reuses their evidence and
keeps observations, invented feedback, financial assumptions and controls apart.
"""
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json

import pandas as pd
import streamlit as st

from workplace import analytics as a, conclusions as x, customer as c, ui as u, visuals as v, portfolio as p
from workplace.feedback import AUDIENCES, feedback_summary
from workplace.peer_view import cached_peer
from workplace.scenarios import room_evidence, evaluate_layout
from workplace.value import business_case
from workplace.overview_view import money

CHAPTERS = [
    ("Overview", "app.py", "The current state", "How are your spaces performing?",
     "See what works. Find the opportunity. Choose the right improvement."),
    ("Spaces", "pages/Spaces.py", "The right space", "The right space for the way people work.",
     "Match investment to real demand, then test a change before committing."),
    ("Feedback", "pages/Feedback.py", "The experience", "Give people a reason to come together.",
     "Listen to employees and guests. Find the friction. Protect what they value."),
    ("Environment", "pages/Environment.py", "The next move", "Turn an observation into an improvement.",
     "One room. One pilot. A measurable change in cost, use and experience."),
]


def enabled():
    return bool(st.session_state.get("presentation_mode", True))


def html(text):
    st.html(text)


def takeaway(title, detail, caution=False):
    html(f'<section class="brief-takeaway {"caution" if caution else ""}"><h2>{escape(title)}</h2><p>{escape(detail)}</p></section>')


def metrics(items):
    """label, value, detail, source, colour, textual value."""
    cards = []
    for label, value, detail, source, colour, words in items:
        cards.append(f'<article class="brief-metric {colour}"><div class="brief-label">{escape(label)}</div>'
                     f'<div class="brief-number {"words" if words else ""}">{escape(str(value))}</div>'
                     f'<div class="brief-detail">{escape(detail)}</div><div class="brief-source {"assumption" if colour == "sunrise" else ""}">{escape(source)}</div></article>')
    html('<div class="brief-metrics">' + ''.join(cards) + '</div>')


def heading(title, subtitle=""):
    html(f'<h2 class="brief-heading">{escape(title)}</h2>' + (f'<div class="brief-small">{escape(subtitle)}</div>' if subtitle else ""))


def steps(rows, done=False):
    html('<div class="brief-flow">' + ''.join(
        f'<div class="brief-action {"done" if done else ""}"><span>{i}</span><div><strong>{escape(title)}</strong><small>{escape(detail)}</small></div></div>'
        for i, (title, detail) in enumerate(rows, 1)) + '</div>')


def finance_case(ctx):
    cases = x.planning_cases(st.session_state, ctx["inventory"]["Room key"])
    with st.sidebar.expander("Savings assumptions"):
        if cases:
            ids = [r["id"] for r in cases]
            chosen = st.session_state.get("overview_case")
            if chosen not in ids:
                st.session_state["overview_case"] = ids[0]
            labels = {r["id"]: f"{r['room']} · {r['currency']}" for r in cases}
            selected = st.selectbox("Business case", ids, format_func=labels.get, **u.field_state("overview_case", ids[0]))
            case = next(r for r in cases if r["id"] == selected)
            st.caption("One room-specific case. Projects and currencies are not added together.")
            if st.button("Edit this case", key="brief_edit_case", width="stretch"):
                st.session_state["selected_room"] = case["room"]
                st.session_state["value_currency"] = case["currency"]
                st.switch_page("pages/Value.py")
            return case
        show = st.toggle("Show illustrative savings", **u.field_state("overview_example", False))
        st.caption("Example only: £18,000 project, £9,000 annual savings and £1,500 extra annual cost. No measured savings or Neat prices are supplied.")
        st.page_link("pages/Value.py", label="Enter a business case", icon=":material/finance_mode:")
        if show:
            return {"example": True, "currency": "GBP", "room": "Illustrative case", **business_case(18000, 9000, 1500, 3)}
    return None


def preferred_room(ctx):
    options = sorted(ctx["inventory"]["Room key"])
    if st.session_state.get("selected_room") not in options:
        fit = x.improvement_summary(ctx)["issues"].query("Kind == 'fit'")
        st.session_state["selected_room"] = fit.iloc[0]["Room key"] if not fit.empty else options[0]
    return options


def room_picker(ctx, label="Room"):
    options = preferred_room(ctx)
    return st.selectbox(label, options, label_visibility="collapsed",
                        **u.field_state("selected_room", options[0]))


def leader_card(portfolio, measure):
    rows = p.room_leaders(portfolio, measure)
    is_use = measure == "usage"
    label = "Most used room" if is_use else "Highest rated room · sample"
    if len(rows) > 1:
        label = "Joint most used rooms" if is_use else "Joint highest rated rooms · sample"
    if rows.empty:
        html(f'<article class="brief-leader"><div class="brief-label">{label}</div><h3>More evidence needed</h3><p>Usage needs 70% coverage and 2 observed hours. Ratings need at least 5 responses.</p></article>')
        return
    row = rows.iloc[0]
    names = " / ".join(p.room_label(n) for n in rows["Room Name"])
    score = f"{row['Utilisation %']:.1f}%" if is_use else f"{row.Sentiment:.2f}<small>/5</small>"
    width = row["Utilisation %"] if is_use else row.Sentiment * 20
    detail = (f"{row['Occupied hours']:.1f} occupied hours · {row['Coverage %']:.0f}% coverage" if is_use
              else f"{row.Responses} invented responses · {row.Positive:.0f}% positive")
    if len(rows) > 1:
        detail = f"{len(rows)} rooms tied at the displayed precision · details on hover"
    source = "Observed time in use" if is_use else "Synthetic space-experience ratings"
    html(f'<article class="brief-leader {"use" if is_use else "rating"}"><div class="brief-label">{label}</div>'
         f'<div class="brief-leader-main"><h3>{escape(names)}</h3><strong>{score}</strong></div>'
         f'<div class="brief-track"><i style="width:{width:.2f}%"></i></div>'
         f'<p>{escape(detail)}</p><span>{source}</span></article>')


def summary(ctx, case):
    controls, audience_col = st.columns([1.25, 1], vertical_alignment="center")
    with controls:
        view = st.segmented_control("Estate view", ["Current state", "Improvement choices"], required=True,
            label_visibility="collapsed", **u.field_state("brief_estate_view", "Current state"))
    with audience_col:
        audience = st.selectbox("Sentiment audience", ["Everyone", *AUDIENCES],
            **u.field_state("feedback_audience", "Everyone"))
    records = c.feedback_in_scope(ctx, audience=audience)
    portfolio = p.room_portfolio(ctx, records)
    feedback = feedback_summary(records)
    candidates = p.opportunity_rows(portfolio)
    telemetry = "Sample telemetry" if ctx["demo"] else "Pulse observations"
    metrics([
        ("Estate time in use", u.fmt(ctx["summary"]["utilisation"], "%", 1), "Occupied / valid observed hours", telemetry, "forest", False),
        ("Positive space ratings", u.fmt(feedback["positive"], "%", 1), f"{feedback['responses']:,} responses · {audience}", "Invented sample feedback · ratings 4–5", "purple", False),
        ("Rooms to review", str(len(candidates)), f"{int(portfolio.Controls.sum())} controls · {int(portfolio.Layout.sum())} layout reviews", "Review signals · routes can overlap", "rain", False),
        ("Annual net saving" if case else "Savings opportunity", money(case["annual_net"], case["currency"]) if case else "To quantify",
         case["room"] if case else "Scope and cost one pilot",
         "Illustrative assumptions" if case and case["example"] else "Entered assumptions" if case else "No measured cost or energy saving", "sunrise", not bool(case)),
    ])
    if view == "Improvement choices":
        improvement_choices(ctx, portfolio)
    else:
        left, right = st.columns([1.9, 1], gap="medium")
        with left, st.container(key="brief_panel_portfolio"):
            heading("Room use meets room experience", "Each bubble is a room · size reflects capacity · colour shows the review route")
            plotted = p.comparison_rows(portfolio)
            if plotted.empty:
                st.info("No room has both enough occupancy evidence and five sample responses in this scope. The separate leaders can still be assessed independently.")
            else:
                fig = p.performance_figure(portfolio, ctx["summary"]["utilisation"], u.FONT)
                st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="brief_portfolio_plot")
                html(f'<div class="brief-small">Showing {len(plotted)} of {len(portfolio)} rooms · rating detail: {fig.layout.meta["rating_axis_floor"]:g}–5 of 5. Dotted lines: estate use and a 4/5 rating. Sentiment is invented.</div>')
        with right:
            leader_card(portfolio, "usage")
            leader_card(portfolio, "sentiment")
            conclusion, _, _ = x.conclusion(ctx, x.improvement_summary(ctx))
            html(f'<div class="brief-insight"><b>The next decision</b>{escape(conclusion)} Open Improvement choices to see the rooms and intervention options.</div>')
    with st.sidebar.expander("How to read the room picture"):
        st.write("Usage leaders need positive capacity, at least 70% occupancy coverage and two observed hours. The estate percentage pools all valid observed hours. Missing time is unknown, not empty.")
        st.write("Sample sentiment leaders need at least five responses and are independent of telemetry coverage. Usage ties use one decimal place; sentiment ties use two. An audience filter changes ratings, never usage or improvement signals.")
        st.write("The map only includes rooms passing both checks. Bubble sizes reflect recorded capacity; colour shows a possible review route. Reference lines are guides, not performance targets. Short periods and sample ratings cannot establish the best room design.")
        st.write("Controls reviews flag warm or lit empty-room observations. Layout reviews flag rooms with two occupied hours and a 90th-percentile group no larger than half their capacity. Both routes require validation before action.")
        st.dataframe(portfolio[["Room key", "Utilisation %", "Coverage %", "Responses", "Sentiment", "Route"]], hide_index=True, width="stretch")


def improvement_choices(ctx, portfolio):
    candidates = p.opportunity_rows(portfolio)
    left, right = st.columns([1, 1.35], gap="medium")
    with left, st.container(key="brief_panel_matrix"):
        heading("Where could a change help?", "Coloured cells show a review signal. A room can have both routes.")
        if candidates.empty:
            st.info("No qualifying controls or layout signals in this scope. Monitor use and collect real feedback before proposing a change.")
        else:
            st.plotly_chart(p.opportunity_figure(portfolio, u.FONT), width="stretch", config={"displayModeBar": False}, key="brief_opportunity_plot")
        limited = int(portfolio["Coverage %"].fillna(0).lt(70).sum())
        html(f'<div class="brief-small">{limited} room(s) below 70% coverage excluded from recommendations. No flag means no qualifying signal in this period.</div>')
    with right, st.container(key="brief_panel_routes"):
        heading("Choose the right intervention")
        if candidates.empty:
            steps([("Strengthen the baseline", "Confirm reporting, room purpose and a representative period."),
                   ("Listen in the space", "Collect real employee and guest feedback."),
                   ("Agree a measurable pilot", "Use, comfort, satisfaction and metered cost before and after.")])
            return
        options = candidates["Room key"].tolist()
        if st.session_state.get("brief_improve_room") not in options:
            previous = st.session_state.get("selected_room")
            st.session_state["brief_improve_room"] = previous if previous in options else options[0]
        room = st.selectbox("Room to improve", options, label_visibility="collapsed",
                            **u.field_state("brief_improve_room", options[0]))
        row = candidates.set_index("Room key").loc[room]
        if row.Controls:
            signals = []
            if row.Warm:
                signals.append(f"{row['Warm hours']:.1f} h warm while empty")
            if row.Light:
                signals.append(f"{row['Light hours']:.1f} h lit while empty")
            signal = " · ".join(signals)
            route_card("01", "Controls / BMS review", signal,
                       "Check schedules and room-to-zone controls; trial occupancy-led HVAC or lighting where suitable.",
                       "Facilities + IT · validate vacancy, bookings, comfort and integration. Meter the result.", "controls")
            if st.button("Explore the controls pilot", key="brief_to_controls", width="stretch"):
                st.session_state["selected_room"] = room
                st.session_state["brief_condition"] = "warm" if row.Warm else "light"
                st.switch_page("pages/Environment.py")
        else:
            html('<div class="brief-small"><b>Controls:</b> no qualifying vacancy-condition signal in this period.</div>')
        if row.Layout:
            seats = max(1, int(row.Capacity / 2))
            evidence = room_evidence(ctx["samples"], room, a.window_hours(ctx["start"], ctx["end"], ctx["office"]))
            replay = evaluate_layout(evidence, [seats])
            route_card("02", "Room configuration review",
                       f"90% of occupied time: {u.fmt(row['P90 attendance'])} people or fewer / {u.fmt(row.Capacity)} seats",
                       f"Test a {seats}-seat option: it fits {u.fmt(replay['fit_percent'], '%', 1)} of observed occupied time.",
                       f"Workplace + IT · observed peak {u.fmt(evidence['peak'])}. Validate demand, purpose, acoustics and accessibility.", "layout")
            if st.button("Compare room layouts", key="brief_to_layout", width="stretch"):
                st.session_state["selected_room"] = room
                st.session_state["brief_space_view"] = "Layout options"
                st.switch_page("pages/Spaces.py")
        else:
            html('<div class="brief-small"><b>Layout:</b> no qualifying capacity-fit signal in this period.</div>')
        with st.popover("What needs validating?", icon=":material/info:", width="stretch"):
            st.write("A BMS link may be an operational change, but it is not automatically simple: existing controls, room-to-zone mapping, permissions, schedules and comfort constraints determine feasibility. Warm or lit does not by itself prove wasted energy.")
            st.write("Reconfiguration is a design and investment decision. Test booking demand, peak groups, room purpose, dimensions, accessibility, acoustics and AV before costing partitions or changing capacity. A second room's future use cannot be inferred from this feed.")
            st.write("Where both routes apply, assess controls feasibility and room purpose first. Use a reversible pilot where appropriate, then decide whether a capital project is justified. Set an owner, budget, baseline and review date.")
            st.caption("The two condition-hour values can overlap. Review routes use telemetry; invented sentiment is not evidence for a building change or financial saving.")


def route_card(number, title, evidence, action, validation, kind):
    html(f'<article class="brief-route {kind}"><div class="brief-route-title"><span>{number}</span><b>{escape(title)}</b></div>'
         f'<strong>{escape(evidence)}</strong><p>{escape(action)}</p><small>{escape(validation)}</small></article>')


def space(ctx, case):
    left, right = st.columns([1.1, 1], gap="medium", vertical_alignment="center")
    with left:
        room = room_picker(ctx)
    r = ctx["stats"].set_index("Room key").loc[room]
    evidence = room_evidence(ctx["samples"], room, a.window_hours(ctx["start"], ctx["end"], ctx["office"]))
    room_capacity = int(r.Capacity) if pd.notna(r.Capacity) and r.Capacity > 0 and int(r.Capacity) == r.Capacity else None
    default = min(100, max(1, int(room_capacity / 2))) if room_capacity else 4
    model_key = "brief_seats_" + sha256(room.encode()).hexdigest()[:12]
    with right:
        with st.popover("Test a smaller-room option", icon=":material/tune:", width="stretch"):
            seats = st.number_input("Proposed room seats", 1, 100, **u.field_state(model_key, default))
            st.caption("Replays observed groups in one proposed room. It does not predict demand, extra meetings or financial savings.")
    layout = evaluate_layout(evidence, [seats])
    view = st.segmented_control("Room view", ["Performance", "Layout options"], required=True,
        label_visibility="collapsed", **u.field_state("brief_space_view", "Performance"))
    if view == "Layout options":
        layout_options(r, evidence, room_capacity, seats, layout)
        return
    title, detail, tone = c.room_story(r)
    takeaway(title, detail, tone == "sunrise")
    left, right = st.columns([1, 1.1], gap="medium")
    with left, st.container(key="brief_panel_seats"):
        heading(f"{r['Room Name']} · {u.fmt(r.Capacity)} seats", "The typical group, drawn against the recorded capacity")
        if room_capacity and pd.notna(r["Typical attendance"]):
            svg = v.room_capacity_svg(r["Typical attendance"], room_capacity).replace(v.BLUE, "#5F259F").replace("Blue represents", "Purple represents")
            st.image(svg, width=350)
        else:
            st.info("Valid attendance and capacity are needed for the room illustration.")
        html(f'<div class="brief-seat-caption"><span><strong>{u.fmt(r["Typical attendance"], digits=1)}</strong>typical people when occupied</span><span><strong>{u.fmt(r["P90 attendance"])}</strong>people or fewer for 90% of occupied time</span></div>')
        html(f'<div class="brief-small">{r["Coverage %"]:.0f}% occupancy coverage · source-clock period above</div>')
    with right, st.container(key="brief_panel_peer"):
        heading("A similar room. Automatically.")
        data = ctx["all_data"]
        if not ctx["demo"]:
            data = data[data.Location.isin(["London EC", "Oslo EC"])]
        pair = cached_peer(data, ctx["fetched"], room, ctx["start"], ctx["end"], ctx["office"])
        if pair:
            html('<div class="brief-pair">' + ''.join(f'<div><span>{escape(row["Room Name"])} · {u.fmt(row.Capacity)} seats</span><strong>{u.fmt(row["Utilisation %"], "%")}</strong><span>time in use · {u.fmt(row["Coverage %"], "%")} coverage</span><span>{escape(row.Location)}</span></div>' for row in pair) + '</div>')
            if any(pd.isna(row["Coverage %"]) or row["Coverage %"] < 70 for row in pair):
                html('<div class="brief-small"><b>Limited coverage:</b> interpret this peer comparison cautiously.</div>')
        else:
            st.write("No capacity peer is available for this period.")
        fit = layout["fit_percent"]
        html(f'<div class="brief-device"><b>A {seats}-seat room would fit {u.fmt(fit, "%", 1)} of observed occupied time.</b>Replay of observed groups; validate peaks, room purpose and accessibility before a change.</div>')
        with st.popover("Evidence and alternatives", icon=":material/info:", width="stretch"):
            st.write(f"Observed peak: {u.fmt(evidence['peak'])} people. The proposed room is exceeded for {u.fmt(layout['exceeds_hours'], ' h', 1)} of occupied time.")
            st.write("The automatic peer uses the closest capacity within 25% or two seats, preferring the same location. The match can come from outside the location filter; dates and operating hours are identical.")
            st.caption("A capacity match does not control for purpose or equipment. Short periods and poor coverage may not represent demand. Empty and unknown time are excluded from the replay.")
            st.page_link("pages/Scenarios.py", label="Explore room alternatives", icon=":material/compare_arrows:")
    html('<div class="brief-small"><b>Suggested improvement:</b> trial the room size people need, while preserving access to larger rooms for peak demand.</div>')


def layout_options(row, evidence, capacity, seats, layout):
    if not capacity:
        st.info("Confirm a positive whole-number room capacity before comparing layouts.")
        return
    heading(f"{row['Room Name']} · test the space around the group", "Same observed attendance, replayed in the current room and one proposed option")
    columns = st.columns(2, gap="medium")
    current = evaluate_layout(evidence, [capacity])
    for column, label, count, result, key in zip(columns, ["Current room", "Smaller-room option"],
            [capacity, seats], [current, layout], ["current", "proposed"]):
        with column, st.container(key="brief_panel_layout_" + key):
            heading(f"{label} · {count} seats")
            if evidence["typical"] is not None:
                svg = v.room_capacity_svg(evidence["typical"], count).replace(v.BLUE, "#5F259F").replace("Blue represents", "Purple represents")
                st.image(svg, width=310)
            fit = result["fit_percent"]
            html(f'<div class="brief-layout-score"><strong>{u.fmt(fit, "%", 1)}</strong><span>of observed occupied time fits</span></div>'
                 f'<div class="brief-track"><i class="lead" style="width:{fit or 0:.2f}%"></i></div>'
                 f'<div class="brief-small">{u.fmt(result["exceeds_hours"], " h", 1)} exceeds this capacity · typical group {u.fmt(evidence["typical"], digits=1)}</div>')
    if evidence["coverage"] is None or evidence["coverage"] < 70:
        st.warning("Limited occupancy coverage: this replay is exploratory. Restore reporting before recommending a layout change.")
    html(f'<div class="brief-insight"><b>Decision gate · observed peak {u.fmt(evidence["peak"])} people</b>'
         'Check peak bookings, purpose, acoustics, accessibility and AV. A smaller footprint may release space; its future use and financial return still need a business case.</div>')
    with st.popover("Alternatives and replay assumptions", icon=":material/compare_arrows:", width="stretch"):
        st.write("Keep the current layout, trial furniture changes, or assess a split-room design. Each requires its own capacity, design and cost assessment. This replay treats each observed count as one group and excludes empty, missing and offline time.")
        st.caption("A second room's demand and simultaneous meetings are unknown. No additional meetings or savings are predicted.")
        st.page_link("pages/Scenarios.py", label="Model one or two rooms", icon=":material/meeting_room:")


def close_survey():
    st.session_state["brief_survey_open"] = False


@st.dialog("Try the Neat Frame survey", width="small", on_dismiss=close_survey)
def survey_dialog(room):
    from workplace.feedback_view import styles, portrait_survey
    styles()
    portrait_survey(room)


def experience(ctx, case):
    audience = st.segmented_control("Feedback audience", ["Everyone", *AUDIENCES], required=True, width="stretch",
                                    label_visibility="collapsed", **u.field_state("feedback_audience", "Everyone"))
    all_records = c.feedback_in_scope(ctx)
    records = all_records if audience == "Everyone" else all_records[all_records.audience.eq(audience)]
    s = feedback_summary(records)
    html('<div class="brief-demo-banner"><b>Sample sentiment:</b> invented responses, matched to the selected rooms and dates. Employees and guests are shown separately.</div>')
    metrics([
        ("Space experience", u.fmt(s["experience"], "/5", 2), "How the space feels", "Sample responses", "purple", False),
        ("Equipment experience", u.fmt(s["equipment"], "/5", 2), "How the technology feels", "Sample responses", "purple", False),
        ("Positive space ratings", u.fmt(s["positive"], "%", 1), "Ratings of 4 or 5", "Sample responses", "forest", False),
        ("Responses in this view", f"{s['responses']:,}", audience, "Synthetic · not live feedback", "rain", False),
    ])
    left, right = st.columns([1, 1.05], gap="medium")
    with left, st.container(key="brief_panel_sentiment"):
        heading("Keep the two experiences visible")
        for group, label in zip(AUDIENCES, ["Neat employees", "Customers / guests"]):
            rows = records[records.audience.eq(group)]
            if audience != "Everyone" and audience != group:
                continue
            scores = feedback_summary(rows)
            positive = scores["positive"] or 0
            neutral = 100 * rows.experience.eq(3).mean() if len(rows) else 0
            low = max(0, 100 - positive - neutral) if len(rows) else 0
            html(f'<div class="brief-audience"><div><span>{label}</span><b>{u.fmt(scores["positive"], "%", 1)}</b></div>'
                 f'<div class="brief-rating-bar"><i style="width:{positive}%;background:#638C7D"></i><i style="width:{neutral}%;background:#DBC684"></i><i style="width:{low}%;background:#9F8884"></i></div><small>Positive space ratings · {len(rows)} sample responses</small></div>')
        html('<div class="brief-small">Green: positive (4–5) · Gold: neutral (3) · Walnut: needs attention (1–2)</div>')
        issues = records.loc[records.issue.ne(""), "issue"].value_counts()
        focus = f"Most frequent sample issue: {issues.index[0]} ({issues.iloc[0]} responses)." if len(issues) else "No issues flagged in this sample selection."
        html(f'<div class="brief-device"><b>Turn feedback into a short improvement list.</b>{escape(focus)} Use a live survey before and after the pilot.</div>')
    with right, st.container(key="brief_panel_frame"):
        html('<div class="brief-frame-layout"><div class="brief-frame" aria-label="Portrait survey concept"><div class="frame-camera"></div><b>How was<br>your visit?</b><small>A few taps. A better workplace.</small><div class="frame-audience">Employee &nbsp; / &nbsp; Guest</div><small>THE SPACE</small><div class="frame-faces">☹ ▫ ☺</div><small>THE EQUIPMENT</small><div class="frame-faces">☹ ▫ ☺</div><div class="frame-send">Share feedback</div></div><div class="brief-frame-copy"><strong>Listen at the moment that matters.</strong><p>Portrait survey concept for Neat Frame. Ask about the room, the equipment and one thing to improve.</p><p><b>Next step:</b> a live pilot with a real response store and an owner for follow-up.</p></div></div>')
        preferred_room(ctx)
        room = st.session_state["selected_room"]
        if st.button("Try the portrait survey", key="brief_try_survey", type="primary", width="stretch"):
            st.session_state["brief_survey_open"] = True
        if st.session_state.get("brief_survey_open", False):
            survey_dialog(ctx["inventory"].set_index("Room key", drop=False).loc[room])


def action_signal(ctx, room, kind):
    findings = x.improvement_summary(ctx)["issues"]
    matching = findings[findings["Room key"].eq(room) & findings.Kind.eq(kind)]
    return None if matching.empty else matching.iloc[0].to_dict()


def simulation_config(ctx, room, kind, signal):
    """The configuration signature prevents a stale result following new filters."""
    return {"mode": "simulation", "room": room, "kind": kind, "start": ctx["start"].isoformat(),
            "end": ctx["end"].isoformat(), "office": ctx["office"], "thresholds": ctx["thresholds"],
            "evidence_hours": signal["Evidence hours"] if signal else None,
            "source_is_demo": ctx["demo"], "command_sent": False, "service_now_ticket_id": None,
            "gateway_acknowledgement": None, "measured_saving": None}


def action(ctx, case):
    left, right = st.columns([1.3, 1], gap="medium", vertical_alignment="center")
    with left:
        room = room_picker(ctx)
    with right:
        kind = st.selectbox("Condition to investigate", ["warm", "light"],
                            format_func=lambda k: "Temperature while empty" if k == "warm" else "Light while empty",
                            label_visibility="collapsed", **u.field_state("brief_condition", "warm"))
    signal = action_signal(ctx, room, kind)
    takeaway("Review the controls, then test a time-limited change." if signal else "Build the evidence before automating a change.",
             "Facilities confirms vacancy, bookings and operating limits. A pilot checks actual energy use and the experience afterwards." if signal else "No finding passes the current evidence rules for this room and condition. Adjust the scope or investigate reporting first.", not bool(signal))
    cols = st.columns([1, 1.35, 1], gap="medium")
    with cols[0], st.container(key="brief_panel_signal"):
        heading("01 · Spot the opportunity")
        hours = u.fmt(signal["Evidence hours"], digits=1) if signal else "—"
        html(f'<div class="brief-evidence-number">{hours}<small> h</small></div>')
        threshold = f"{ctx['thresholds']['warm']:g} °C" if kind == "warm" else f"{ctx['thresholds']['bright']:g} lux"
        html(f'<div class="brief-small"><b>Observed empty time above {threshold}</b><br>{escape(room)}</div>')
        html('<div class="brief-device"><b>Investigate, then act.</b>Temperature and light readings do not establish equipment operation or energy consumption.</div>')
    config = simulation_config(ctx, room, kind, signal)
    signature = json.dumps(config, sort_keys=True)
    result = st.session_state.get("brief_workflow")
    completed = bool(result and result["signature"] == signature)
    with cols[1], st.container(key="brief_panel_workflow"):
        heading("02 · Connect the response", "Control workflow demonstration · no live commands")
        if st.button("Replay the simulated workflow", key="brief_run", type="primary", width="stretch", disabled=not bool(signal)):
            st.session_state["brief_workflow"] = {"signature": signature, "payload": {**config,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "stages": ["Observation attached", "Simulated policy review", "Simulated temporary override", "Verification would be required"]}}
            completed = True
        steps([
            ("Observe · Pulse reporting feed", "Attach the selected room's historical evidence."),
            ("Review · ServiceNow workflow", "Would check current vacancy, bookings and policy."),
            ("Act · building controls gateway", "Would request a 15-minute " + ("HVAC standby override." if kind == "warm" else "lighting override.")),
            ("Verify · close the loop", "Would check actual state, energy and fresh feedback."),
        ], completed)
        html('<div class="brief-small"><b>' + ("Simulation replayed. No command sent or saving measured." if completed else "A configured integration and site approval would be needed for a live pilot.") + '</b></div>')
    with cols[2], st.container(key="brief_panel_value"):
        heading("03 · Prove the value")
        if case:
            html(f'<div class="brief-source assumption">{"ILLUSTRATIVE" if case["example"] else "ENTERED"} FINANCIAL ASSUMPTIONS</div>'
                 f'<div class="brief-evidence-number" style="color:#5F259F;font-size:34px">{money(case["annual_net"], case["currency"])}</div>'
                 f'<div class="brief-small">Annual net benefit · {escape(case["room"])}</div>')
            payback = "No payback" if case["payback_months"] is None else f"{case['payback_months']:.1f} months"
            html(f'<div class="brief-device"><b>{escape(payback)} simple payback</b>{money(case["project_cost"], case["currency"])} initial investment · {money(case["net_benefit"], case["currency"])} {case["years"]}-year net benefit.</div>')
            html('<div class="brief-small">Separate planning case; the control simulation does not generate these savings.</div>')
        else:
            html('<div class="brief-evidence-number" style="font-size:31px;color:#4C515C">Cost the pilot</div><div class="brief-small">Add costs and cash-saving assumptions, then compare the outcome with the baseline.</div>')
            if st.button("Show illustrative savings", key="brief_show_savings", width="stretch"):
                st.session_state["overview_example"] = True
                st.rerun()
        with st.popover("Pilot measures & assumptions", icon=":material/info:", width="stretch"):
            st.write("Agree one room, a baseline period, facilities and IT owners, a budget and a review date. Compare actual metered energy/cost, room use, comfort and real employee/guest feedback before and after.")
            st.write("For live control, commission room-to-zone mapping, permissions, interlocks, current vacancy and booking checks. Restore the normal schedule when the override expires or occupancy changes. Controller acknowledgement is not proof of savings.")
            if case:
                st.write(f"Annual savings {money(case['annual_savings'], case['currency'])} less extra annual cost {money(case['annual_extra_cost'], case['currency'])}. The model excludes discounting, tax, inflation and residual value.")
                if case["payback_months"] is not None and case["payback_months"] > case["years"] * 12:
                    st.caption("Payback falls beyond the assessment period.")
            st.page_link("pages/Value.py", label="Open the full investment model", icon=":material/finance_mode:")


def run(active):
    index = next(i for i, row in enumerate(CHAPTERS) if row[0] == active)
    _, _, _, title, subtitle = CHAPTERS[index]
    u.shell(active, title, subtitle, briefing=True)
    with st.sidebar.expander("Scope & data"):
        ctx = u.context(show_evidence=False, compact=True)
    case = finance_case(ctx)
    locations = ", ".join(sorted(ctx["inventory"].Location.unique()))
    scope = f"{locations} · {ctx['start']:%d %b}–{ctx['end']:%d %b %Y} · {'Office hours' if ctx['office'] else 'All hours'} · {len(ctx['inventory'])} rooms"
    html(f'<div class="brief-scope"><span>{escape(scope)}</span><b>{"DEMO telemetry" if ctx["demo"] else "Pulse observations"} · {u.fmt(ctx["summary"]["coverage"], "%")} coverage</b></div>')
    {"Overview": summary, "Spaces": space, "Feedback": experience, "Environment": action}[active](ctx, case)
    endings = ["Approve one pilot. Measure what changes.", "Use observed demand to test the room mix.",
               "Turn a moment of feedback into a better next visit.", "Start with one room. Prove the benefit. Then scale."]
    left, right = st.columns([2.4, 1], vertical_alignment="center")
    with left:
        html(f'<div class="brief-end"><span><strong>{index+1:02d} / 04</strong> &nbsp; {endings[index]}</span></div><div class="brief-proof">Feedback is synthetic · Costs are assumptions · Controls are simulated</div>')
    with right:
        following = CHAPTERS[(index+1) % len(CHAPTERS)]
        st.page_link(following[1], label=("Next: " if index < 3 else "Return to ") + following[2].lower(), icon=":material/arrow_forward:", width="stretch")
