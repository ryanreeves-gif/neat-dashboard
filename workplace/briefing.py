"""Five compact chapters for a ten-minute executive demonstration.

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
    ("Office opportunity", "pages/Next_Steps.py", "Office opportunity", "More value from the whole office.",
     "Review running costs. Explore a better room mix. Validate one office-wide programme."),
]


def enabled():
    return bool(st.session_state.get("presentation_mode", True))


def html(text):
    st.html(text)


def takeaway(title, detail, caution=False):
    html(f'<section class="brief-takeaway {"caution" if caution else ""}"><h2>{escape(title)}</h2><p>{escape(detail)}</p></section>')


def metrics(items, stacked=False, first_card=None):
    """label, value, detail, source, colour, textual value."""
    cards = []
    for label, value, detail, source, colour, words in items:
        cards.append(f'<article class="brief-metric {colour}"><div class="brief-label">{escape(label)}</div>'
                     f'<div class="brief-number {"words" if words else ""}">{escape(str(value))}</div>'
                     f'<div class="brief-detail">{escape(detail)}</div><div class="brief-source {"assumption" if colour == "sunrise" else ""}">{escape(source)}</div></article>')
    if first_card is not None:
        cards[0] = first_card
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
    room_filter = st.session_state.get("room_filter", [])
    room_value = u.fmt(ctx["summary"]["utilisation"], "%", 1)
    if len(room_filter) == 1:
        selected_name = room_filter[0].split(" / ")[-1]
        utilisation_card = (f'<article class="brief-metric forest utilisation-card"><div class="brief-label">UTILISATION · {escape(selected_name)}</div>'
            f'<div class="brief-number">{escape(room_value)}</div><div class="brief-detail">Room time in use · valid observations</div>'
            f'<div class="brief-source">{telemetry} · selected room</div></article>')
    else:
        present = a.any_room_occupied_percent(ctx["samples"], a.window_hours(ctx["start"], ctx["end"], ctx["office"]))
        office_value = "≥" + u.fmt(present, "%", 1) if pd.notna(present) else "—"
        utilisation_card = (f'<article class="brief-metric forest utilisation-card"><div class="brief-label">UTILISATION</div>'
            f'<div class="utilisation-pair"><div><div class="brief-number">{escape(office_value)}</div><div class="brief-detail">Office time in use</div></div>'
            f'<div><div class="brief-number">{escape(room_value)}</div><div class="brief-detail">Average room use</div></div></div>'
            f'<div class="brief-source">{telemetry} · any monitored room / valid room-hours</div></article>')
    metrics([
        ("Room time in use", u.fmt(ctx["summary"]["utilisation"], "%", 1),
         f"Any monitored room occupied: ≥{u.fmt(a.any_room_occupied_percent(ctx["samples"], a.window_hours(ctx["start"], ctx["end"], ctx["office"])), "%", 1)} of scheduled time" if ctx["summary"]["valid_hours"] > 0 else "Any monitored room: no occupancy data", telemetry + " · not whole-office occupancy", "forest", False),
        ("Positive space ratings", u.fmt(feedback["positive"], "%", 1), f"{feedback['responses']:,} responses · {audience}", "Invented sample feedback · ratings 4–5", "purple", False),
        ("Rooms to review", str(len(candidates)), f"{int(portfolio.Controls.sum())} controls · {int(portfolio.Layout.sum())} layout reviews", "Review signals · routes can overlap", "rain", False),
        ("Annual net saving" if case else "Savings opportunity", money(case["annual_net"], case["currency"]) if case else "To quantify",
         case["room"] if case else "Scope and cost one pilot",
         "Illustrative assumptions" if case and case["example"] else "Entered assumptions" if case else "No measured cost or energy saving", "sunrise", not bool(case)),
    ], first_card=utilisation_card)
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
        st.write("Office time in use is a minimum share of scheduled time with at least one monitored room occupied; overlap is counted once. Missing observations remain unknown and open areas are not measured. Average room use pools occupied room-hours over valid observed room-hours. Usage leaders need 70% coverage and two observed hours.")
        st.write("Sample sentiment leaders need at least five responses and are independent of telemetry coverage. Usage ties use one decimal place; sentiment ties use two. An audience filter changes ratings, never usage or improvement signals.")
        st.write("The performance comparison chart only includes rooms passing both checks. Bubble sizes reflect recorded capacity; colour shows a possible review route. Reference lines are guides, not performance targets. Short periods and sample ratings cannot establish the best room design.")
        st.write("Controls reviews flag warm or bright empty-room observations. Lux cannot prove electric lights were on. Layout reviews flag rooms with two occupied hours and a 90th-percentile group no larger than half their capacity. Both routes require validation before action.")
        st.dataframe(portfolio[["Room key", "Utilisation %", "Coverage %", "Responses", "Sentiment", "Route"]], hide_index=True, width="stretch")


def space(ctx, case):
    from workplace import office_map
    if office_map.applies(ctx):
        map_column, comparison = st.columns([1, 1.45], gap="medium")
        with comparison:
            room = room_picker(ctx)
        with map_column, st.container(key="brief_panel_fit_map"):
            office_map.render_fit(ctx, room)
        with comparison, st.container(key="brief_fit_comparison"):
            space_comparison(ctx, room)
    else:
        space_comparison(ctx, room_picker(ctx))


def space_comparison(ctx, room):
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


def layout_options(row, evidence, capacity, seats, layout, qualifies, compact=False):
    if not capacity:
        st.info("Confirm a positive whole-number room capacity before comparing layouts.")
        return
    html('<div class="brief-seat-legend"><i></i>Purple people show the average group while occupied; grey shows remaining seats.</div>')
    columns = st.columns(2, gap="medium")
    current = evaluate_layout(evidence, [capacity])
    for column, label, count, result, key in zip(columns, ["Current room", "Smaller-room option"],
            [capacity, seats], [current, layout], ["current", "proposed"]):
        with column, st.container(key="brief_panel_layout_" + key):
            heading(f"{label} · {count} seats")
            if evidence["typical"] is not None:
                svg = v.room_capacity_svg(evidence["typical"], count).replace(v.BLUE, "#5F259F").replace("Blue represents", "Purple represents")
                st.image(svg, width=240 if compact else 310)
            fit = result["fit_percent"]
            html(f'<div class="brief-layout-score"><strong>{u.fmt(fit, "%", 1)}</strong><span>of observed occupied time fits</span></div>'
                 f'<div class="brief-track"><i class="lead" style="width:{fit or 0:.2f}%"></i></div>'
                 f'<div class="brief-small">{u.fmt(result["exceeds_hours"], " h", 1)} exceeds this capacity · typical group {u.fmt(evidence["typical"], digits=1)}</div>')
    if evidence["coverage"] is None or evidence["coverage"] < 70:
        st.warning("Limited occupancy coverage: this replay is exploratory. Restore reporting before recommending a layout change.")
    next_step = ("Next step: check bookings and peak groups before a layout trial." if qualifies
                 else "Next step: establish representative demand before recommending a change.")
    if compact:
        html(f'<div class="brief-small"><b>Observed peak: {u.fmt(evidence["peak"])} people.</b> Confirm how larger groups will be accommodated before changing the room.</div>')
    else:
        html(f'<div class="brief-insight"><b>{next_step}</b>'
             f'Observed peak: {u.fmt(evidence["peak"])} people. Workplace + IT should confirm room purpose, accessibility and AV.</div>')


def experience(ctx, case):
    from workplace.feedback_view import styles, portrait_survey
    from workplace import office_map
    styles()
    all_records = c.feedback_in_scope(ctx)
    audience = st.session_state.get("feedback_audience", "Everyone")
    records = all_records if audience == "Everyone" else all_records[all_records.audience.eq(audience)]
    mapped = office_map.applies(ctx)
    with st.container(key="brief_experience_workspace" if mapped else "brief_experience_standard"):
        html('<div class="brief-demo-banner"><b>Sample results:</b> invented responses aligned to the selected rooms and dates. Companion test submissions stay separate.</div>')
        if mapped:
            map_column, overview, companion = st.columns([1, 1.05, 1.15], gap="medium")
            with map_column, st.container(key="brief_panel_experience_map"):
                room = experience_room(ctx)
                office_map.render_experience(ctx, records, room, audience)
        else:
            overview, companion = st.columns([1.35, 1], gap="large")
        with overview:
            heading("Sentiment overview", f'{len(ctx["inventory"])} rooms in the current filters · {audience}')
            experience_overview(records, audience)
            if not mapped:
                room = experience_room(ctx)
        with companion, st.container(key="brief_companion"):
            html('<div class="brief-companion-label">COMPANION APP · READY TO TRY</div>')
            portrait_survey(ctx["inventory"].set_index("Room key", drop=False).loc[room], compact=True)
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


def experience_room(ctx):
    options = preferred_room(ctx)
    return st.selectbox("Room on the companion app", options, **u.field_state("selected_room", options[0]))


def experience_overview(records, audience):
    """Keep the overall filtered story visible when a map room is selected."""
    s = feedback_summary(records)
    metrics([
        ("Space experience", u.fmt(s["experience"], "/5", 2), "How the space feels", "Sample responses", "purple", False),
        ("Equipment experience", u.fmt(s["equipment"], "/5", 2), "How the technology feels", "Sample responses", "purple", False),
        ("Positive space ratings", u.fmt(s["positive"], "%", 1), "Ratings of 4 or 5", "Sample responses", "forest", False),
        ("Responses in this view", f"{s['responses']:,}", audience, "Synthetic · not live feedback", "rain", False),
    ], stacked=True)
    with st.container(key="brief_panel_sentiment"):
        heading("Employees and guests")
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
        html('<div class="brief-insight"><b>Close the feedback loop</b>Workplace + IT: review recurring issues, act, then compare real employee and guest feedback before and after.</div>')


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


def improve_recommendation(ctx, room, plan):
    row = ctx["stats"].set_index("Room key").loc[room]
    focus = plan["focus"]
    if focus == "Operating schedules":
        signals = []
        for kind, label in [("warm", "warm"), ("light", "bright")]:
            signal = action_signal(ctx, room, kind)
            if signal:
                signals.append(f'{signal["Evidence hours"]:.1f} h {label} while recorded empty')
        evidence = " · ".join(signals)
        note = "Validate actual controls, then trial one approved schedule change. Temperature and lux alone do not establish wasted energy."
    elif focus == "Room layout":
        evidence = f'90% of occupied time had {u.fmt(row["P90 attendance"])} people or fewer · {u.fmt(row.Capacity)} seats'
        note = plan["gate"]
    else:
        evidence = f'{u.fmt(row["Coverage %"], "%")} occupancy coverage · {u.fmt(row["Observed hours"], " h", 1)} observed'
        note = "No qualifying intervention is established in this scope. Check reporting and representative demand."
    tone = {"Operating schedules": "controls", "Room layout": "layout", "Evidence baseline": "evidence"}[focus]
    html(f'<article class="improve-recommendation {tone}"><div class="brief-label">RECOMMENDED FIRST STEP · {escape(plan["name"])}</div>'
         f'<h2>{escape(plan["title"])}</h2><div class="improve-evidence">{escape(evidence)}</div>'
         f'<p>{escape(note)}</p></article>')


def improve_controls(ctx, room):
    from workplace.control_demo import KINDS, scenario, animation_html
    import streamlit.components.v1 as components

    if st.session_state.get("brief_control_room") != room:
        st.session_state["brief_control_room"] = room
        st.session_state["brief_condition"] = "warm" if action_signal(ctx, room, "warm") else "light"
    with st.container(key="brief_control_settings"):
        control, target, time = st.columns([1.2, 1.15, 1], gap="small")
        with control:
            kind = st.selectbox("Control to simulate", list(KINDS), format_func=KINDS.get,
                                **u.field_state("brief_condition", "warm"))
        temperature = st.session_state.get("brief_ac_target", 21.0)
        brightness = st.session_state.get("brief_light_target", 20)
        boost = st.session_state.get("brief_air_boost", 80)
        with target:
            if kind == "warm":
                temperature = st.slider("AC setpoint (°C)", 16.0, 28.0, step=.5, **u.field_state("brief_ac_target", temperature))
            elif kind == "light":
                brightness = st.slider("Lighting output (%)", 0, 100, step=10, **u.field_state("brief_light_target", brightness))
            else:
                boost = st.slider("Ventilation boost (%)", 20, 100, step=10, **u.field_state("brief_air_boost", boost))
        with time:
            duration = st.slider("Duration (minutes)", 5, 60, step=5, **u.field_state("brief_control_minutes", 15))
    with ctx["tools"].expander("Simulation assumptions"):
        start_temperature = st.number_input("Starting room temperature (demo °C)", min_value=10.0, max_value=40.0, step=.5,
                                            **u.field_state("brief_start_temperature", 26.0))
        st.caption("Starting controls and response curves are invented. Lux does not prove lights are on; the air indicator is not measured CO₂ or a health score.")
    signal = action_signal(ctx, room, kind)
    if signal is None:
        html('<div class="brief-small">This control is an exploratory example; the selected observations do not establish a need for it.</div>')
    settings = scenario(kind, duration, temperature, brightness, boost, start_temperature)
    config = {**simulation_config(ctx, room, kind, signal), "settings": settings}
    signature = json.dumps(config, sort_keys=True)
    result = st.session_state.get("brief_workflow")
    if result and result["signature"] != signature:
        st.session_state.pop("brief_workflow", None)
        result = None
    target_label = f"{temperature:g}°C" if kind == "warm" else f"{brightness}% output" if kind == "light" else f"{boost}% boost"
    if st.button(f"Run simulation · {KINDS[kind]} · {target_label} · {duration} min", key="brief_run", type="primary", width="stretch"):
        result = {"signature": signature, "payload": {**config, "created_at": datetime.now(timezone.utc).isoformat(),
                  "stages": ["Demo request", "Simulated review", "Simulated override", "Assumed schedule restored"]}}
        st.session_state["brief_workflow"] = result
    name = ctx["inventory"].set_index("Room key").loc[room, "Room Name"]
    components.html(animation_html(settings, name, result["payload"]["created_at"] if result else None,
                                   compact=True), height=255, scrolling=True)
    return result


def improve_layout(ctx, room):
    row = ctx["stats"].set_index("Room key").loc[room]
    evidence = room_evidence(ctx["samples"], room, a.window_hours(ctx["start"], ctx["end"], ctx["office"]))
    capacity = int(row.Capacity) if pd.notna(row.Capacity) and row.Capacity > 0 and int(row.Capacity) == row.Capacity else None
    default = min(100, max(1, int(capacity / 2))) if capacity else 4
    key = "brief_seats_" + sha256(room.encode()).hexdigest()[:12]
    setting, explanation = st.columns([1, 2], vertical_alignment="center")
    with setting:
        seats = st.number_input("Proposed room seats", 1, 100, **u.field_state(key, default))
    with explanation:
        html('<div class="brief-small">Try a reversible layout first. This replays observed groups; it does not predict future demand or savings.</div>')
    layout_options(row, evidence, capacity, seats, evaluate_layout(evidence, [seats]), True, compact=True)


def improve_value(plan, case, room):
    matched = scoped_case(case, room)
    financial = (f'{money(matched["annual_net"], matched["currency"])} annual net · entered assumptions, not measured'
                 if matched else "Financial value to quantify · no measured saving")
    html('<div class="improve-value">'
         f'<div><span>Potential benefit</span><b>{escape(plan["benefit"])}</b><small>{escape(financial)}</small></div>'
         f'<div><span>Owner</span><b>{escape(plan["owner"])}</b><small>Agree a baseline, budget and review date.</small></div>'
         f'<div><span>Success measure</span><b>{escape(plan["measure"])}</b><small>Measure before and after the pilot.</small></div></div>')


def action(ctx, case):
    from workplace import office_map
    with st.container(key="brief_improve_workspace"):
        left, right = st.columns([1, 2.1], gap="medium")
        with left, st.container(key="brief_panel_improve_map"):
            room = room_picker(ctx)
            if office_map.applies(ctx):
                office_map.render_improve(ctx, room)
            else:
                heading("Choose where to start")
                html('<div class="brief-small">Follow the selected room from observations to a practical next step. The office map is available for London EC.</div>')
        options = pilot_options(ctx, room)
        route_key = "brief_route_" + sha256(room.encode()).hexdigest()[:12]
        if st.session_state.get(route_key) not in options:
            st.session_state[route_key] = options[0]
        with right, st.container(key="brief_panel_improve_action"):
            focus = options[0]
            if len(options) > 1:
                labels = {"Operating schedules": "Controls review", "Room layout": "Room layout"}
                focus = st.segmented_control("Review route", options, format_func=labels.get,
                                             selection_mode="single", required=True, label_visibility="collapsed",
                                             **u.field_state(route_key, options[0]))
            plan = pilot_plan(ctx, room, focus)
            improve_recommendation(ctx, room, plan)
            result = None
            if plan["focus"] == "Operating schedules":
                result = improve_controls(ctx, room)
            else:
                st.session_state.pop("brief_workflow", None)
                if plan["focus"] == "Room layout":
                    improve_layout(ctx, room)
                else:
                    steps([("Check reporting", "Validate sensor coverage and the room's intended purpose."),
                           ("Understand demand", "Collect a representative period of occupancy and bookings, including peak groups."),
                           ("Listen to users", "Capture real employee and guest feedback. Sample sentiment cannot validate a room change.")])
        improve_value(plan, case, room)
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


def run(active):
    index = next(i for i, row in enumerate(CHAPTERS) if row[0] == active)
    _, _, _, title, subtitle = CHAPTERS[index]
    tools = u.shell(active, title, subtitle, briefing=True)
    if tools is None:
        tools = st.sidebar
    with st.container(key="brief_filters"):
        ctx = u.context(show_evidence=False, sidebar_details=True, details_container=tools)
    ctx["tools"] = tools
    with tools:
        st.selectbox("Sentiment audience", ["Everyone", *AUDIENCES], **u.field_state("feedback_audience", "Everyone"))
    case = None if active == "Office opportunity" else finance_case(ctx)
    locations = ", ".join(sorted(ctx["inventory"].Location.unique()))
    # The analysis boundary can be midnight on the following day; show the
    # inclusive calendar date selected in the filter instead.
    scope = f"{locations} · {ctx['start']:%d %b}–{ctx['end_date']:%d %b %Y} · {'Office hours' if ctx['office'] else 'All hours'} · {len(ctx['inventory'])} rooms"
    held = f' · Held snapshot {ctx["fetched"]:%H:%M}' if st.session_state.get("hold_observations") else ""
    html(f'<div class="brief-scope"><span>{escape(scope)}</span><b>{"DEMO telemetry" if ctx["demo"] else "Pulse observations"} · {u.fmt(ctx["summary"]["coverage"], "%")} coverage{held}</b></div>')
    from workplace.decision import render as decision
    {"Overview": summary, "Spaces": space, "Feedback": experience, "Environment": action, "Office opportunity": decision}[active](ctx, case)
    endings = ["Approve one pilot. Measure what changes.", "Use observed demand to test the room mix.",
               "Turn a moment of feedback into a better next visit.", "Test the response, then agree the next step.",
               "Validate the office plan. Pilot the changes. Measure the outcome."]
    left, right = st.columns([2.4, 1], vertical_alignment="center")
    with left:
        html(f'<div class="brief-end"><span><strong>{index+1:02d} / {len(CHAPTERS):02d}</strong> &nbsp; {endings[index]}</span></div><div class="brief-proof">Feedback is synthetic · Costs are assumptions · Controls are simulated</div>')
    with right:
        following = CHAPTERS[(index+1) % len(CHAPTERS)]
        st.page_link(following[1], label=("Next: " if index < len(CHAPTERS) - 1 else "Return to ") + following[2].lower(), icon=":material/arrow_forward:", width="stretch")
