"""A readable closing screen; evidence, proposed action and value stay distinct."""
from hashlib import sha256
from html import escape

import pandas as pd
import streamlit as st

from workplace import analytics as a, customer as c, portfolio as p, ui as u
from workplace.feedback import AUDIENCES, feedback_summary
from workplace.pilot import pilot_plan, scoped_case
from workplace.scenarios import room_evidence, evaluate_layout
from workplace.overview_view import money


def closing_evidence(ctx, records, room, state, case=None):
    """Reuse the same eligibility, scope and per-room proposal as the other pages."""
    portfolio = p.room_portfolio(ctx, records)
    winners = p.room_leaders(portfolio, "usage")
    demand = dict(value="—", title="More usage evidence needed",
                  detail="Confirm reporting before identifying a leading room.")
    if not winners.empty:
        names = " / ".join(winners["Room Name"]) if len(winners) <= 2 else f"{len(winners)} rooms tied"
        demand = dict(value=u.fmt(winners.iloc[0]["Utilisation %"], "%", 1),
                      title=f'{names} · {"joint most used" if len(winners) > 1 else "most used"}',
                      detail="Time in use during valid observations. Protect availability where demand is strongest.")
    audience = state.get("feedback_audience", "Everyone")
    cohorts = []
    for group, name in zip(AUDIENCES, ["Employees", "Customers / guests"]):
        if audience != "Everyone" and audience != group:
            continue
        score = feedback_summary(records[records.audience.eq(group)])
        cohorts.append(dict(name=name, count=score["responses"],
                            value=u.fmt(score["positive"], "%", 1) if score["responses"] >= 5 else "—"))
    token = sha256(room.encode()).hexdigest()[:12]
    plan = pilot_plan(ctx, room, state.get("brief_route_" + token))
    row = ctx["stats"].set_index("Room key").loc[room]
    opportunity = dict(value=u.fmt(row["Coverage %"], "%"), title=f'{plan["name"]} · check the evidence',
                       detail="No qualifying intervention in this scope. Confirm reporting, demand and room purpose.",
                       source="Occupancy coverage")
    if plan["focus"] == "Operating schedules":
        from workplace.briefing import action_signal
        preferred = state.get("brief_condition") if state.get("brief_control_room") == room else None
        kinds = list(dict.fromkeys([preferred, "warm", "light"]))
        for kind in kinds:
            if kind not in {"warm", "light"}:
                continue
            signal = action_signal(ctx, room, kind)
            if signal:
                condition = "Warm" if kind == "warm" else "Bright"
                opportunity = dict(value=u.fmt(signal["Evidence hours"], " h", 1),
                    title=f'{plan["name"]} · review controls',
                    detail=f"{condition} while recorded empty. Verify actual controls before changing the schedule.",
                    source="Observed condition · not proof of wasted energy")
                break
    elif plan["focus"] == "Room layout":
        capacity = row.Capacity
        if pd.notna(capacity) and capacity > 0 and int(capacity) == capacity:
            seats = state.get("brief_seats_" + token, min(100, max(1, int(capacity / 2))))
            evidence = room_evidence(ctx["samples"], room, a.window_hours(ctx["start"], ctx["end"], ctx["office"]))
            layout = evaluate_layout(evidence, [seats])
            opportunity = dict(value=f"{int(capacity)} → {seats}", title=f'{plan["name"]} · proposed seats',
                detail=f'{u.fmt(layout["fit_percent"], "%", 1)} of observed occupied time fits. Peak: {u.fmt(evidence["peak"])} people; check larger-group needs.',
                source="Replay of observed groups · not a demand forecast")
    return dict(demand=demand, cohorts=cohorts, opportunity=opportunity, plan=plan,
                case=scoped_case(case, room))


def render(ctx, case):
    from workplace.briefing import preferred_room
    preferred_room(ctx)
    room = st.session_state["selected_room"]
    audience = st.session_state.get("feedback_audience", "Everyone")
    records = c.feedback_in_scope(ctx, audience=audience)
    model = closing_evidence(ctx, records, room, st.session_state, case)
    demand, opportunity, plan = model["demand"], model["opportunity"], model["plan"]
    source = "Demonstration telemetry" if ctx["demo"] else "Pulse observations"
    cohort_html = "".join(
        f'<div><strong>{escape(row["value"])}</strong><span>{escape(row["name"])}</span>'
        f'<small>{row["count"]} sample responses</small></div>' for row in model["cohorts"])
    next_step = {
        "Operating schedules": "Validate the controls. Trial one schedule change.",
        "Room layout": "Validate demand. Trial a reversible layout.",
        "Evidence baseline": "Establish a reliable baseline before investing.",
    }[plan["focus"]]
    matched = model["case"]
    value = (f'Entered estimate: {money(matched["annual_net"], matched["currency"])} annual net benefit · not measured.'
             if matched else "Financial benefit to quantify with a baseline and a costed pilot.")
    with st.container(key="decision_workspace"):
        st.html('<div class="decision-grid">'
            '<article class="decision-card demand"><div class="decision-kicker">01 · PROTECT WHAT WORKS</div>'
            f'<div class="decision-number">{escape(demand["value"])}</div><h2>{escape(demand["title"])}</h2>'
            f'<p>{escape(demand["detail"])}</p><div class="decision-source">{source}</div></article>'
            '<article class="decision-card people"><div class="decision-kicker">02 · LISTEN TO PEOPLE</div>'
            f'<div class="decision-cohorts">{cohort_html}</div><h2>Positive space ratings</h2>'
            '<p>Validate the pattern with real feedback.</p>'
            '<div class="decision-source">Invented sample feedback · ratings 4–5<br>— means fewer than 5 responses</div></article>'
            '<article class="decision-card opportunity"><div class="decision-kicker">03 · TEST ONE IMPROVEMENT</div>'
            f'<div class="decision-number">{escape(opportunity["value"])}</div><h2>{escape(opportunity["title"])}</h2>'
            f'<p>{escape(opportunity["detail"])}</p><div class="decision-source">{escape(opportunity["source"])}</div></article></div>')
        st.html(f'<section class="decision-proposal"><div class="decision-kicker">PROPOSED NEXT STEP · {escape(room)}</div>'
            f'<h2>{escape(next_step)}</h2><div class="decision-owners"><div><span>OWNER</span><b>{escape(plan["owner"])}</b></div>'
            f'<div><span>SUCCESS MEASURE</span><b>{escape(plan["measure"])}</b></div></div>'
            f'<p class="decision-value"><strong>Value to prove: {escape(plan["benefit"]).lower()}.</strong> {escape(value)}</p></section>')
    with ctx["tools"].expander("Conclusion evidence"):
        st.write(f"Following {room} and its review route from Improve. Use the shared filters to change the scope; use Improve to choose another room or route.")
        st.write(plan["gate"])
        st.caption("A proposal, not an approved or completed project. Agree a baseline, budget and review date before the pilot. No measured savings or after-results are connected.")
