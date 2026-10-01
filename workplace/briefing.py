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

from workplace import analytics as a, conclusions as x, customer as c, ui as u, visuals as v
from workplace.feedback import AUDIENCES, feedback_summary
from workplace.peer_view import cached_peer
from workplace.scenarios import room_evidence, evaluate_layout
from workplace.value import business_case
from workplace.overview_view import money

CHAPTERS = [
    ("Overview", "app.py", "The conclusion", "Earn the commute. Make every space count.",
     "Better spaces for people. Better decisions for the business."),
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


def summary(ctx, case):
    improvements = x.improvement_summary(ctx)
    title, detail, tone = x.conclusion(ctx, improvements)
    takeaway(title, detail, tone == "sunrise")
    feedback = feedback_summary(c.feedback_in_scope(ctx))
    ranking, leader = x.room_type_ranking(ctx), x.leading_room(ctx)
    tops = x.leaders(ranking)
    top = tops.iloc[0] if len(tops) else None
    fit = improvements["counts"]["fit"]
    source = "Sample feedback · invented" if feedback["responses"] else "No samples in this scope"
    metrics([
        ("Room-fit improvements", str(fit), "Rooms to review against peak demand", "Sample telemetry" if ctx["demo"] else "Pulse observations", "forest", False),
        ("User sentiment", u.fmt(feedback["experience"], "/5", 2), f"{feedback['responses']:,} sample responses", source, "purple", False),
        ("Most-used room size" if len(ranking) != 1 else "Only qualifying room size",
         "Joint leaders" if len(tops) > 1 else top["Room type"].split(" · ")[0] if top is not None else "Unassessed",
         f"{top['Time in use %']:.1f}% of observed time in use" if top is not None else "More evidence needed", "Capacity bands · observed use", "rain", True),
        ("Annual net saving" if case else "Savings available", money(case["annual_net"], case["currency"]) if case else "To quantify",
         (case["room"] if case else "Start with one costed pilot"),
         "Illustrative assumptions" if case and case["example"] else "Entered assumptions" if case else "Cost inputs needed", "sunrise", not bool(case)),
    ])
    left, right = st.columns([1, 1], gap="medium")
    with left, st.container(key="brief_panel_demand"):
        heading("Learn from the spaces people use", "Time in use · capacity bands, not room-purpose categories")
        if ranking.empty:
            st.info("No room types pass the observation checks in this scope.")
        else:
            html(''.join(f'<div class="brief-rank"><span>{escape(r["Room type"])}</span><div class="brief-track"><i class="{"lead" if i == 0 else ""}" style="width:{r["Time in use %"]:.3f}%"></i></div><strong>{r["Time in use %"]:.1f}%</strong></div>' for i, r in ranking.iterrows()))
        if leader:
            names = " + ".join(leader["equipment"]["video"]) or "Equipment model unconfirmed"
            html(f'<div class="brief-device"><b>{escape(leader["Room Name"])} · {escape(names)}</b>'
                 f'{leader["Utilisation %"]:.1f}% time in use · current equipment in {"a joint-leading" if leader["joint"] else "the leading"} room. Device use and quality are not measured.</div>')
        with st.sidebar.expander("Ranking evidence"):
            st.write("Each included room has positive capacity, at least 70% occupancy coverage and two observed hours. Group scores pool hours. A single category has no comparison winner; ties are retained at one decimal place.")
            st.caption("Room purpose, bookings and equipment may differ. Equipment is the inventory snapshot at the selected end, not a historical installation record.")
            st.dataframe(ranking, hide_index=True, width="stretch")
    with right, st.container(key="brief_panel_priorities"):
        heading("Three changes worth testing")
        counts = improvements["counts"]
        limited = improvements["limited"]
        first = (f"Review {fit} room-fit candidate{'s' if fit != 1 else ''}", "Workplace · test a smaller-room option against peaks and purpose.") if fit else ("Build a representative demand baseline", "Workplace · review peak attendance, purpose and booking demand.")
        second = ("Investigate how empty rooms are run", f"Facilities · {counts['warm']} temperature and {counts['light']} lighting reviews; counts can overlap.") if counts['warm'] or counts['light'] else ("Protect comfort and readiness", "Facilities + IT · review room conditions and reporting gaps.")
        if limited:
            first = (first[0], first[1] + f" Restore coverage in {limited} excluded room(s).")
        steps([first, second, ("Listen before and after the change", "People + IT · collect real employee and guest feedback; remove the recurring friction.")])
        html('<div class="brief-small"><b>Decision to take:</b> approve one pilot with an owner, budget and review date.</div>')


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
