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
from workplace.pilot import pilot_options, pilot_plan, scoped_case

CHAPTERS = [
    ("Overview", "app.py", "The current state", "How are your spaces performing?",
     "Understand demand. Protect the experience. Decide where to invest."),
    ("Spaces", "pages/Spaces.py", "The right space", "Does the room fit the group?",
     "Match investment to real demand, then test a change before committing."),
    ("Feedback", "pages/Feedback.py", "The experience", "Give people a reason to come together.",
     "Listen to employees and guests. Find the friction. Protect what they value."),
    ("Environment", "pages/Environment.py", "The next move", "What should we do next?",
     "One room. One practical change. A result you can measure."),
]


def enabled():
    return bool(st.session_state.get("presentation_mode", True))


def html(text):
    st.html(text)


def takeaway(title, detail, caution=False):
    html(f'<section class="brief-takeaway {"caution" if caution else ""}"><h2>{escape(title)}</h2><p>{escape(detail)}</p></section>')


def metrics(items, stacked=False):
    """label, value, detail, source, colour, textual value."""
    cards = []
    for label, value, detail, source, colour, words in items:
        cards.append(f'<article class="brief-metric {colour}"><div class="brief-label">{escape(label)}</div>'
                     f'<div class="brief-number {"words" if words else ""}">{escape(str(value))}</div>'
                     f'<div class="brief-detail">{escape(detail)}</div><div class="brief-source {"assumption" if colour == "sunrise" else ""}">{escape(source)}</div></article>')
    html(f'<div class="brief-metrics {"stacked" if stacked else ""}">' + ''.join(cards) + '</div>')


def heading(title, subtitle=""):
    html(f'<h2 class="brief-heading">{escape(title)}</h2>' + (f'<div class="brief-small">{escape(subtitle)}</div>' if subtitle else ""))


def steps(rows, done=False):
    html('<div class="brief-flow">' + ''.join(
        f'<div class="brief-action {"done" if done else ""}"><span>{i}</span><div><strong>{escape(title)}</strong><small>{escape(detail)}</small></div></div>'
        for i, (title, detail) in enumerate(rows, 1)) + '</div>')


def finance_case(ctx):
    cases = x.planning_cases(st.session_state, ctx["inventory"]["Room key"])
    with ctx["tools"].expander("Savings assumptions"):
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
    if len(rows) > 2:
        names = f"{len(rows)} rooms tied"
    score = f"{row['Utilisation %']:.1f}%" if is_use else f"{row.Sentiment:.2f}<small>/5</small>"
    width = row["Utilisation %"] if is_use else row.Sentiment * 20
    detail = (f"{row['Occupied hours']:.1f} occupied hours · {row['Coverage %']:.0f}% coverage" if is_use
              else f"{row.Responses} invented responses · {row.Positive:.0f}% positive")
    if len(rows) > 1:
        detail = f"{len(rows)} rooms tied · full scores in Presenter tools"
    source = "Observed time in use" if is_use else "Synthetic space-experience ratings"
    html(f'<article class="brief-leader {"use" if is_use else "rating"}"><div class="brief-label">{label}</div>'
         f'<div class="brief-leader-main"><h3>{escape(names)}</h3><strong>{score}</strong></div>'
         f'<div class="brief-track"><i style="width:{width:.2f}%"></i></div>'
         f'<p>{escape(detail)}</p><span>{source}</span></article>')


def summary(ctx, case):
    audience = st.session_state.get("feedback_audience", "Everyone")
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
    from workplace import office_map
    if office_map.applies(ctx):
        office_map.render(ctx, portfolio)
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
            preferred_room(ctx)
            plan = pilot_plan(ctx, st.session_state["selected_room"])
            html(f'<article class="brief-recommendation"><div class="brief-label">RECOMMENDED NEXT STEP · {escape(plan["name"])}</div>'
                 f'<h3>{escape(plan["title"])}</h3>'
                 f'<small><b>Owner</b> {escape(plan["owner"])}<br><b>Measure</b> {escape(plan["measure"])}</small></article>')
    with ctx["tools"].expander("Room evidence and methodology"):
        st.write("Usage leaders need positive capacity, at least 70% occupancy coverage and two observed hours. The estate percentage pools all valid observed hours. Missing time is unknown, not empty.")
        st.write("Sample sentiment leaders need at least five responses and are independent of telemetry coverage. Usage ties use one decimal place; sentiment ties use two. An audience filter changes ratings, never usage or improvement signals.")
        st.write("The performance comparison chart only includes rooms passing both checks. Bubble sizes reflect recorded capacity; colour shows a possible review route. Reference lines are guides, not performance targets. Short periods and sample ratings cannot establish the best room design.")
        st.write("Controls reviews flag warm or bright empty-room observations. Lux cannot prove electric lights were on. Layout reviews flag rooms with two occupied hours and a 90th-percentile group no larger than half their capacity. Both routes require validation before action.")
        st.dataframe(portfolio[["Room key", "Utilisation %", "Coverage %", "Responses", "Sentiment", "Route"]], hide_index=True, width="stretch")


def space(ctx, case):
    room = room_picker(ctx)
    r = ctx["stats"].set_index("Room key").loc[room]
    evidence = room_evidence(ctx["samples"], room, a.window_hours(ctx["start"], ctx["end"], ctx["office"]))
    capacity = int(r.Capacity) if pd.notna(r.Capacity) and r.Capacity > 0 and int(r.Capacity) == r.Capacity else None
    default = min(100, max(1, int(capacity / 2))) if capacity else 4
    model_key = "brief_seats_" + sha256(room.encode()).hexdigest()[:12]
    with ctx["tools"].expander("Room comparison settings"):
        seats = st.number_input("Proposed room seats", 1, 100, **u.field_state(model_key, default))
        st.caption("Replays observed groups. It does not predict new bookings, savings or demand for a second room.")
        st.page_link("pages/Scenarios.py", label="Explore other layouts", icon=":material/compare_arrows:")
    layout = evaluate_layout(evidence, [seats])
    qualifies = "Room layout" in pilot_options(ctx, room)
    if qualifies:
        takeaway(f'{r["Room Name"]}: most groups need fewer seats.',
                 f'90% of occupied time had {u.fmt(r["P90 attendance"])} people or fewer in this {u.fmt(r.Capacity)}-seat room.')
    else:
        takeaway("Check the demand before changing the layout.",
                 "This view does not establish a room-size recommendation. The comparison below is exploratory.", True)
    layout_options(r, evidence, capacity, seats, layout, qualifies)
    data = ctx["all_data"]
    if not ctx["demo"]:
        data = data[data.Location.isin(["London EC", "Oslo EC"])]
    pair = cached_peer(data, ctx["fetched"], room, ctx["start"], ctx["end"], ctx["office"])
    if pair:
        comparison = " · ".join(f'{item["Room Name"]} ({item.Location}): {u.fmt(item["Utilisation %"], "%")} in use' for item in pair)
        html(f'<div class="brief-small"><b>Similar-size room:</b> {escape(comparison)}. Capacity match only; purpose and location can differ.</div>')


def layout_options(row, evidence, capacity, seats, layout, qualifies):
    if not capacity:
        st.info("Confirm a positive whole-number room capacity before comparing layouts.")
        return
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
    next_step = ("Next step: check bookings and peak groups before a layout trial." if qualifies
                 else "Next step: establish representative demand before recommending a change.")
    html(f'<div class="brief-insight"><b>{next_step}</b>'
         f'Observed peak: {u.fmt(evidence["peak"])} people. Workplace + IT should confirm room purpose, accessibility and AV.</div>')


def experience(ctx, case):
    from workplace.feedback_view import styles, portrait_survey
    styles()
    all_records = c.feedback_in_scope(ctx)
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        audience = st.session_state.get("feedback_audience", "Everyone")
        records = all_records if audience == "Everyone" else all_records[all_records.audience.eq(audience)]
        s = feedback_summary(records)
        html('<div class="brief-demo-banner"><b>Sample results:</b> invented responses aligned to the selected rooms and dates. Test submissions appear separately below.</div>')
        metrics([
            ("Space experience", u.fmt(s["experience"], "/5", 2), "How the space feels", "Sample responses", "purple", False),
            ("Equipment experience", u.fmt(s["equipment"], "/5", 2), "How the technology feels", "Sample responses", "purple", False),
            ("Positive space ratings", u.fmt(s["positive"], "%", 1), "Ratings of 4 or 5", "Sample responses", "forest", False),
            ("Responses in this view", f"{s['responses']:,}", audience, "Synthetic · not live feedback", "rain", False),
        ], stacked=True)
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
        html(f'<div class="brief-small"><b>{escape(focus)}</b></div>')
        html('<div class="brief-insight"><b>Close the feedback loop</b>Workplace + IT: assign recurring issues, make a change, then compare real employee and guest feedback. These samples demonstrate the method; they do not establish satisfaction.</div>')
    with left:
        options = preferred_room(ctx)
        room = st.selectbox("Room on the companion app", options, **u.field_state("selected_room", options[0]))
        latest = st.session_state.get("feedback_tryouts", [])
        if latest:
            response = latest[-1]
            html(f'<div class="brief-test-receipt"><b>Your latest test · {escape(response["room_name"])}</b>'
                 f'{escape(response["audience"])} · Space {response["experience"]}/5 · Equipment {response["equipment"]}/5'
                 '<small>Saved in this browser session only · historical sample scores stay separate</small></div>')
        with ctx["tools"].expander("Companion deployment details"):
            st.write("The companion is ready to try here. Choose employee or guest, rate the space and equipment, then share feedback. Use Next person to clear the form for the next visitor.")
            st.write("For deployment, validate the web app on Neat Frame, connect an authenticated response store and agree who follows up on feedback and IT-help requests. Hardware touch behaviour and live integrations have not been tested.")
            st.page_link("pages/Frame.py", label="Open the full portrait screen", icon=":material/open_in_full:")
    with right, st.container(key="brief_companion"):
        html('<div class="brief-companion-label">COMPANION APP · READY TO TRY</div>')
        portrait_survey(ctx["inventory"].set_index("Room key", drop=False).loc[room], compact=True)


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
    from workplace.control_demo import KINDS, scenario, animation_html
    import streamlit.components.v1 as components

    room = room_picker(ctx)
    plan = pilot_plan(ctx, room)
    options = pilot_options(ctx, room)
    with ctx["tools"].expander("Simulation settings"):
        kind = st.selectbox("Control to simulate", list(KINDS), format_func=KINDS.get,
                            **u.field_state("brief_condition", "warm"))
        temperature = st.slider("AC setpoint (°C)", 16.0, 28.0, step=.5, **u.field_state("brief_ac_target", 21.0))
        brightness = st.slider("Lighting output (%)", 0, 100, step=10, **u.field_state("brief_light_target", 20))
        boost = st.slider("Ventilation boost (%)", 20, 100, step=10, **u.field_state("brief_air_boost", 80))
        duration = st.slider("Override duration (minutes)", 5, 60, step=5, **u.field_state("brief_control_minutes", 15))
        start_temperature = st.number_input("Starting room temperature (demo °C)", min_value=10.0, max_value=40.0, step=.5,
                                            **u.field_state("brief_start_temperature", 26.0))
        st.caption("Starting controls and response curves are invented. Lux does not prove lights are on; the air indicator is not measured CO₂ or a health score.")
    signal = action_signal(ctx, room, kind)
    row = ctx["inventory"].set_index("Room key").loc[room]
    settings = scenario(kind, duration, temperature, brightness, boost, start_temperature)
    config = {**simulation_config(ctx, room, kind, signal), "settings": settings}
    signature = json.dumps(config, sort_keys=True)
    result = st.session_state.get("brief_workflow")
    if result and result["signature"] != signature:
        st.session_state.pop("brief_workflow", None)
        result = None
    left, right = st.columns([1, 1.5], gap="medium")
    with left, st.container(key="brief_panel_recommendation"):
        html(f'<div class="brief-label">RECOMMENDED FIRST STEP · {escape(plan["name"])}</div>'
             f'<h2 class="brief-direct-answer">{escape(plan["title"])}</h2>')
        findings = x.improvement_summary(ctx)["issues"]
        findings = findings[findings["Room key"].eq(room)]
        if plan["focus"] == "Operating schedules":
            warm = findings[findings.Kind.eq("warm")]
            light = findings[findings.Kind.eq("light")]
            observed = warm.iloc[0] if not warm.empty else light.iloc[0]
            condition = "warm" if observed.Kind == "warm" else "bright"
            html(f'<div class="brief-why"><strong>{observed["Evidence hours"]:.1f} h</strong><span>{condition} while recorded empty</span></div>')
            st.caption("A reason to check actual controls and schedules; not proof of wasted energy.")
        else:
            html(f'<div class="brief-small">{escape(plan["action"])}</div>')
        steps([( "Check", plan["gate"]), ("Try", plan["action"]), ("Measure", plan["measure"])])
        html(f'<div class="brief-owner"><b>Owner</b><span>{escape(plan["owner"])}</span></div>')
        if "Room layout" in options and plan["focus"] != "Room layout":
            html('<div class="brief-small"><b>Then consider the layout.</b> Validate bookings and peak demand before spending on a smaller-room design.</div>')
        html('<div class="brief-small"><b>Value to prove:</b> better use and experience, with any cost saving measured against the baseline.</div>')
    with right, st.container(key="brief_panel_control_preview"):
        heading("See how a response could work", "Illustrative example · no commands are sent")
        target = f"{temperature:g}°C" if kind == "warm" else f"{brightness}% output" if kind == "light" else f"{boost}% boost"
        if st.button(f"Run example · {KINDS[kind]} · {target} · {duration} min", key="brief_run", type="primary", width="stretch"):
            result = {"signature": signature, "payload": {**config, "created_at": datetime.now(timezone.utc).isoformat(),
                      "stages": ["Demo request", "Simulated review", "Simulated override", "Assumed schedule restored"]}}
            st.session_state["brief_workflow"] = result
        components.html(animation_html(settings, row["Room Name"], result["payload"]["created_at"] if result else None), height=505, scrolling=False)
    with ctx["tools"].expander("Pilot details and business case"):
        st.write(plan["success"])
        st.caption("Agree targets, budget and review date. Collect real feedback, bookings and actual energy/cost before and after. No measured pilot outcome is connected here.")
        matched = scoped_case(case, room)
        if matched:
            st.write(f'Entered case for {room}: {money(matched["annual_net"], matched["currency"])} annual net benefit. Assumptions only; not measured.')
        else:
            st.write("Financial return is still to quantify for this room. Enter the project cost, expected cash benefit and ongoing cost.")
        st.page_link("pages/Value.py", label="Cost this room's pilot", icon=":material/finance_mode:")
        st.caption("A live control link needs room-to-zone mapping, permissions, comfort limits and facilities ownership. The simulation creates no ticket, acknowledgement or measured saving.")
        if st.button("Reset simulation", key="brief_reset", disabled=result is None):
            st.session_state.pop("brief_workflow", None)
            st.rerun()
    html('<div class="brief-closing"><b>Start with one room. Make one change. Measure the difference.</b><span>Agree the owner, baseline and review date before starting.</span></div>')


def run(active):
    index = next(i for i, row in enumerate(CHAPTERS) if row[0] == active)
    _, _, _, title, subtitle = CHAPTERS[index]
    tools = u.shell(active, title, subtitle, briefing=True)
    with st.container(key="brief_filters"):
        ctx = u.context(show_evidence=False, sidebar_details=True, details_container=tools)
    ctx["tools"] = tools
    with tools:
        st.selectbox("Sentiment audience", ["Everyone", *AUDIENCES], **u.field_state("feedback_audience", "Everyone"))
    case = finance_case(ctx)
    locations = ", ".join(sorted(ctx["inventory"].Location.unique()))
    # The analysis boundary can be midnight on the following day; show the
    # inclusive calendar date selected in the filter instead.
    scope = f"{locations} · {ctx['start']:%d %b}–{ctx['end_date']:%d %b %Y} · {'Office hours' if ctx['office'] else 'All hours'} · {len(ctx['inventory'])} rooms"
    held = f' · Held snapshot {ctx["fetched"]:%H:%M}' if st.session_state.get("hold_observations") else ""
    html(f'<div class="brief-scope"><span>{escape(scope)}</span><b>{"DEMO telemetry" if ctx["demo"] else "Pulse observations"} · {u.fmt(ctx["summary"]["coverage"], "%")} coverage{held}</b></div>')
    {"Overview": summary, "Spaces": space, "Feedback": experience, "Environment": action}[active](ctx, case)
    endings = ["Approve one pilot. Measure what changes.", "Use observed demand to test the room mix.",
               "Turn a moment of feedback into a better next visit.", "Start with one room. Prove the benefit. Then scale."]
    left, right = st.columns([2.4, 1], vertical_alignment="center")
    with left:
        html(f'<div class="brief-end"><span><strong>{index+1:02d} / 04</strong> &nbsp; {endings[index]}</span></div><div class="brief-proof">Feedback is synthetic · Costs are assumptions · Controls are simulated</div>')
    with right:
        following = CHAPTERS[(index+1) % len(CHAPTERS)]
        st.page_link(following[1], label=("Next: " if index < 3 else "Return to ") + following[2].lower(), icon=":material/arrow_forward:", width="stretch")
