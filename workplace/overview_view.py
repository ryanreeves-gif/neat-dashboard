"""The dashboard's conclusion, with drill-downs behind each decision."""
from html import escape
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from workplace import ui as u, visuals as v, customer as c
from workplace import conclusions as x
from workplace.feedback import AUDIENCES, feedback_summary
from workplace.value import business_case


def money(value, currency):
    symbol = {"GBP": "£", "EUR": "€", "NOK": "kr "}[currency]
    return f"{'−' if value < 0 else ''}{symbol}{abs(value):,.0f}"


def claim(label, value, detail, source, tone, numeric=False):
    st.html(f'<article class="overview-claim {tone}"><div class="claim-label">{escape(label)}</div>'
            f'<div class="claim-value {"numeric" if numeric else ""}">{escape(value)}</div>'
            f'<p>{escape(detail)}</p><span class="source-tag {tone}">{escape(source)}</span></article>')


def rank_bars(ranking):
    rows = []
    best = set(x.leaders(ranking)["Room type"])
    for _, r in ranking.iterrows():
        rows.append(f'<div class="rank-row"><div><strong>{escape(r["Room type"])}</strong>'
                    f'<span>{int(r.Rooms)} room{"s" if r.Rooms != 1 else ""} · {r.Observed:.1f} observed h</span></div>'
                    f'<b>{r["Time in use %"]:.1f}%</b></div><div class="rank-track">'
                    f'<i class="{"leader" if r["Room type"] in best else ""}" style="width:{r["Time in use %"]:.3f}%"></i></div>')
    st.html('<div class="room-ranks" aria-label="Room types ranked by observed time in use">' + ''.join(rows) + '</div>')


def savings_panel(ctx, improvements, cases, case):
    with st.container(key="panel_overview_savings"):
        st.subheader("Where the savings could come from")
        counts = improvements["counts"]
        st.html('<div class="opportunity-strip">' + ''.join(
            f'<div><strong>{counts[k]}</strong><span>{label}</span></div>'
            for k, label in [("fit", "room-fit reviews"), ("warm", "temperature reviews"), ("light", "lighting reviews")]) + '</div>')
        st.caption("Counts can overlap. Facilities signals identify investigations; check controls and meters before assigning savings.")
        if cases:
            if len(cases) > 1:
                ids = [r["id"] for r in cases]
                labels = {r["id"]: f"{r['room']} · {r['currency']}" for r in cases}
                st.selectbox("Business case to summarise", ids, format_func=labels.get,
                             **u.field_state("overview_case", case["id"]))
            st.caption(f"One business case: {case['room']} · {case['currency']}. Projects and currencies are kept separate.")
        else:
            st.toggle("Show illustrative savings example", **u.field_state("overview_example", False))
        if case:
            tag = "Illustrative assumptions · example only" if case["example"] else "Entered assumptions · projected outcome"
            st.html(f'<span class="source-tag assumption">{tag}</span>')
            st.markdown(f"**{money(case['annual_net'], case['currency'])} annual net cash benefit**")
            st.caption(f"{money(case['annual_savings'], case['currency'])} expected annual savings less "
                       f"{money(case['annual_extra_cost'], case['currency'])} extra running cost. "
                       "The initial investment is shown separately below.")
            payback = "No payback" if case["payback_months"] is None else f"{case['payback_months']:.1f} months"
            st.html('<div class="case-facts">' + ''.join(
                f'<div><span>{escape(label)}</span><strong>{escape(value)}</strong></div>' for label, value in [
                    ("Initial investment", money(case["project_cost"], case["currency"])),
                    ("Simple payback", payback),
                    (f"{case['years']}-year net benefit", money(case["net_benefit"], case["currency"]))]) + '</div>')
            if case["payback_months"] is not None and case["payback_months"] > case["years"] * 12:
                st.caption("Payback is beyond the assessment period.")
            st.caption("A planning case to validate in a pilot. No measured financial savings are connected.")
        else:
            st.markdown("**Savings have not been costed yet.**")
            st.write("Start with a room-fit or facilities pilot. Enter its cost and expected cash benefit to show the annual saving and payback here.")
        fit = improvements["issues"].query("Kind == 'fit'")
        if not fit.empty:
            row = fit.iloc[0]
            st.caption(f"Room-fit starting point: {row['Room key']} · {row.Evidence}")
            if st.button("Explore the priority room", key="fit_room", width="stretch"):
                u.go_room(row["Room key"])
        if cases:
            if st.button("Edit this business case", key="overview_edit_case", icon=":material/finance_mode:", width="stretch"):
                st.session_state["selected_room"] = case["room"]
                st.session_state["value_currency"] = case["currency"]
                st.switch_page("pages/Value.py")
        else:
            st.page_link("pages/Value.py", label="Build the investment case", icon=":material/finance_mode:")


def performance_panel(ctx, ranking, leader):
    with st.container(key="panel_overview_performance"):
        st.subheader("What is working hardest")
        st.caption("Room types ranked by time in use · observed occupied hours ÷ observed hours")
        if ranking.empty:
            st.info("No room types have enough observation coverage to compare in this period.")
        else:
            rank_bars(ranking)
            if len(ranking) == 1:
                st.caption("Only one room type qualifies. There is no comparison winner.")
            elif len(x.leaders(ranking)) > 1:
                st.caption("The leading types are tied at the displayed precision.")
        if leader:
            equipment = leader["equipment"]
            name = " + ".join(equipment["video"]) or "Device model not identified"
            label = "One of the busiest rooms" if leader["joint"] else "Busiest qualifying room"
            st.html(f'<div class="device-spotlight"><span>{label}</span><h3>{escape(leader["Room Name"])}</h3>'
                    f'<strong>{leader["Utilisation %"]:.1f}% time in use</strong><p>{escape(name)}</p></div>')
            st.caption("Device highlight = the current equipment in this room. Room activity does not measure device use, quality or financial return.")
            if st.button("See the leading room", key="overview_leading_room", width="stretch"):
                u.go_room(leader["Room key"])
        with st.expander("How to interpret the comparison"):
            st.write("Room types are capacity bands, not recorded room-purpose categories. Each included room has at least 70% occupancy coverage and two observed hours. Scores pool hours rather than average percentages.")
            st.write("Higher use indicates demand to investigate. Check peak attendance, comfort, bookings and room purpose before treating a configuration as a design to repeat. Small groups and single-room categories are descriptive evidence only.")
            st.caption(f"{len(x.eligible_rooms(ctx))} of {len(ctx['stats'])} selected rooms qualify. Missing or zero capacity, short observation periods and limited coverage are excluded.")
            if leader:
                st.write(f"Equipment snapshot: {leader['Room key']} · {leader['equipment_timestamp']:%d %b %Y, %H:%M} source clock. This is not a record of which devices were installed throughout the selected period.")
                if leader["equipment"]["other"]:
                    st.caption("Also reported: " + ", ".join(leader["equipment"]["other"]))
                if leader["equipment"]["unmapped"]:
                    st.caption("Unmapped equipment codes, retained without guessing: " + ", ".join(leader["equipment"]["unmapped"]))
            st.markdown("Device names: [Neat model guide](https://support.neat.no/article/neat-device-attributes-for-microsoft-intune-conditional-access-device-exclusions/) · [Microsoft device list](https://learn.microsoft.com/en-us/microsoftteams/devices/certified-hardware-android).")


def sentiment_panel(records, sentiment):
    with st.container(key="panel_overview_people"):
        st.html('<span class="source-tag sample">Sample feedback · all responses are synthetic</span>')
        left, right = st.columns([1, 1.5], gap="large")
        with left:
            st.subheader("How people feel about the experience")
            if sentiment["responses"]:
                st.markdown(f"**{sentiment['positive']:.1f}% positive space ratings** across {sentiment['responses']:,} sample responses.")
                st.caption(f"Space: {sentiment['experience']:.2f}/5 · Equipment: {sentiment['equipment']:.2f}/5. Positive = 4 or 5 out of 5.")
                employee = feedback_summary(records[records.audience.eq(AUDIENCES[0])])
                guest = feedback_summary(records[records.audience.eq(AUDIENCES[1])])
                if employee["responses"] and guest["responses"] and guest["positive"] > employee["positive"]:
                    st.write("The demonstration tells a positive story, with guests rating the spaces most favourably. A live survey would show which parts of that experience to protect as rooms change.")
                else:
                    st.write("Use this demonstration to plan a live survey, then track whether room changes improve the experience for employees and guests.")
            else:
                st.write("No sample feedback falls within these room, date and operating-hour filters.")
            st.page_link("pages/Feedback.py", label="Explore employee and guest feedback", icon=":material/arrow_forward:")
        with right:
            if sentiment["responses"]:
                fig = go.Figure()
                labels = ["Employees", "Customers / guests"]
                for ratings, name, colour in [([4, 5], "Positive · 4–5", "#638C7D"), ([3], "Neutral · 3", "#DBC684"), ([1, 2], "Needs attention · 1–2", "#9F8884")]:
                    values, hover = [], []
                    for audience in AUDIENCES:
                        group = records[records.audience.eq(audience)]
                        values.append(100 * group.experience.isin(ratings).mean() if len(group) else 0)
                        hover.append(len(group))
                    fig.add_trace(go.Bar(y=labels, x=values, orientation="h", name=name, marker_color=colour,
                                         customdata=hover, text=[f"{v:.1f}%" if v >= 10 else "" for v in values],
                                         textposition="inside", hovertemplate="%{y}<br>%{x:.1f}%<br>%{customdata} sample responses<extra>%{fullData.name}</extra>"))
                u.plot_style(fig, 205)
                fig.update_layout(barmode="stack", bargap=.5, legend=dict(orientation="h", y=-.35, font_size=10), margin=dict(l=0, r=0, t=5, b=45))
                fig.update_xaxes(range=[0, 100], ticksuffix="%", showgrid=True, dtick=25)
                fig.update_yaxes(autorange="reversed", showgrid=False)
                st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="overview_sentiment")
                for audience, label in zip(AUDIENCES, labels):
                    n = int(records.audience.eq(audience).sum())
                    st.caption(f"{label}: {n} sample responses" if n else f"{label}: no sample responses in this scope")
        st.caption("Sample opinions follow the selected rooms and dates. They are not evidence of actual customer satisfaction or a financial benefit.")


def render(executive_panel):
    u.shell("Overview", "The story. The opportunity. The next move.",
            "Your conclusion on savings, room performance and the experience — with a clear plan for what to improve.")
    v.styles()
    ctx = u.context()
    improvements = x.improvement_summary(ctx)
    ranking, leader = x.room_type_ranking(ctx), x.leading_room(ctx)
    records = c.feedback_in_scope(ctx)
    sentiment = feedback_summary(records)
    cases = x.planning_cases(st.session_state, ctx["inventory"]["Room key"])
    case = next((r for r in cases if r["id"] == st.session_state.get("overview_case")), cases[0] if cases else None)
    if case:
        st.session_state["overview_case"] = case["id"]
    elif st.session_state.get("overview_example", False):
        case = {"example": True, "currency": "GBP", "room": "Illustration only", **business_case(18000, 9000, 1500, 3)}
    title, detail, tone = x.conclusion(ctx, improvements)
    c.answer("The conclusion for this period", title, detail, tone,
             str(improvements["rooms"]), "rooms with changes to investigate")
    if improvements["limited"]:
        st.caption(f"{improvements['limited']} room(s) have limited coverage and are excluded from the improvement and performance highlights.")
    top_types = x.leaders(ranking)
    cols = st.columns(4, gap="medium")
    with cols[0]:
        if case:
            claim("Projected annual net saving", money(case["annual_net"], case["currency"]),
                  (case["room"] + " · " if cases else "Example only · ") + "after extra running costs",
                  "Illustrative example" if case["example"] else "Entered assumptions", "assumption", True)
        else:
            claim("Savings available", "To quantify", "Cost a priority improvement to reveal its saving and payback.", "Not yet assessed", "assumption")
    with cols[1]:
        value = "More evidence needed" if top_types.empty else (top_types.iloc[0]["Room type"] if len(top_types) == 1 else "Joint leaders")
        detail = "A comparable demand baseline is needed." if top_types.empty else f"{top_types.iloc[0]['Time in use %']:.1f}% of observed time in use"
        claim("Most-used room type" if len(ranking) != 1 else "Only room type in scope", value, detail, "Pulse · capacity bands", "forest")
    with cols[2]:
        equipment = leader["equipment"]["video"] if leader else []
        value = equipment[0] if len(equipment) == 1 else "Mixed device setup" if equipment else "Model not identified"
        detail = f"{leader['Room Name']} · {leader['Utilisation %']:.1f}% time in use" if leader else "No room qualifies for a use comparison."
        claim("Device in a leading room" if leader and leader["joint"] else "Device in the leading room", value, detail, "Room-use association", "rain")
    with cols[3]:
        claim("User sentiment score", f"{sentiment['experience']:.2f}/5" if sentiment["responses"] else "No responses",
              f"{sentiment['positive']:.1f}% positive · {sentiment['responses']:,} responses" if sentiment["responses"] else "No samples within these filters",
              "Sample feedback", "sample", bool(sentiment["responses"]))
    st.write("")
    left, right = st.columns([1, 1], gap="medium")
    with left: savings_panel(ctx, improvements, cases, case)
    with right: performance_panel(ctx, ranking, leader)
    st.write("")
    sentiment_panel(records, sentiment)
    executive_panel(ctx)
    with st.expander("Supporting utilisation evidence"):
        c.time_mix_chart(ctx["summary"])
        st.page_link("pages/Spaces.py", label="Explore attendance and demand patterns", icon=":material/meeting_room:")
    u.footer()
