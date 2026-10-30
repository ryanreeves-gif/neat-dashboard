"""Customer-facing summaries built from the same evidence as the detailed views."""
from html import escape
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from workplace import ui as u

PURPOSE = {
    "Overview": "Your executive conclusion",
    "Spaces": "Match your rooms to real demand",
    "Feedback": "Understand the people using your spaces",
    "Environment": "Improve comfort and investigate running costs",
    "Insights": "Turn evidence into an improvement plan",
    "Scenarios": "Test room changes before committing",
    "Value & ROI": "Build a transparent investment case",
    "Operations": "Keep rooms ready for people",
    "Ask the data": "Find an answer and the next step",
}


def answer(kicker, title, detail="", tone="forest", value=None, label=""):
    fact = f'<div class="answer-fact"><strong>{escape(str(value))}</strong><span>{escape(label)}</span></div>' if value is not None else ""
    st.html(f'<section class="answer {tone}"><div><div class="answer-kicker">{escape(kicker)}</div><h2>{escape(title)}</h2>'
            f'{"<p>" + escape(detail) + "</p>" if detail else ""}</div>{fact}</section>')


def stat(label, value, detail, tone="rain", source=None):
    tag = ""
    if source:
        kind = "sample" if "sample" in source.lower() else "assumption" if "assum" in source.lower() else ""
        tag = f'<div class="source-tag {kind}">{escape(source)}</div>'
    st.html(f'<article class="value-stat {tone}">{tag}<div class="label">{escape(label)}</div><div class="number">{escape(str(value))}</div><div class="detail">{escape(detail)}</div></article>')


def time_mix(summary):
    expected = max(0.0, float(summary["expected_hours"]))
    observed = min(expected, max(0.0, float(summary["valid_hours"])))
    occupied = min(observed, max(0.0, float(summary["occupied_hours"])))
    return pd.DataFrame({"State": ["Occupied", "Observed empty", "Unknown"],
                         "Hours": [occupied, observed - occupied, expected - observed]})


def time_mix_chart(summary, key="estate_time_mix"):
    data = time_mix(summary)
    fig = go.Figure(go.Pie(labels=data.State, values=data.Hours, hole=.76, sort=False,
        marker=dict(colors=["#638C7D", "#DCE5E8", "#F1E8D4"], line=dict(color="white", width=3)),
        textinfo="none", hovertemplate="%{label}<br>%{value:.1f} room-hours<br>%{percent} of scheduled time<extra></extra>"))
    u.plot_style(fig, 250)
    fig.update_layout(showlegend=False, margin=dict(l=0,r=0,t=5,b=5),
        annotations=[dict(x=.5,y=.55,text=u.fmt(summary["utilisation"], "%"),showarrow=False,font=dict(size=44,color="#1A1C21")),
                     dict(x=.5,y=.39,text="of observed time in use",showarrow=False,font=dict(size=11,color="#4C515C"))])
    st.plotly_chart(fig, width="stretch", config={"displayModeBar":False}, key=key)
    st.caption("Ring segments include unknown time. The centre percentage uses observed time only.")
    st.html('<div class="visual-legend">' + ''.join(f'<span><i style="background:{c}"></i>{r.State} <strong>{r.Hours:.1f} h</strong></span>'
        for (_,r),c in zip(data.iterrows(),["#638C7D","#DCE5E8","#F1E8D4"])) + '</div>')


def room_story(row):
    if pd.isna(row["Utilisation %"]):
        return "Build a usable baseline for this room.", "Valid occupancy observations are needed before comparing use or changing its layout.", "sunrise"
    if pd.isna(row["Coverage %"]) or row["Coverage %"] < 70:
        return "Close the observation gaps before changing this room.", "The room has limited coverage in this period. Investigate reporting first, then reassess attendance and peaks.", "sunrise"
    if row["Occupied hours"] == 0:
        return "No occupied time was observed in this room.", "Check bookings and the room's purpose before treating the observed empty time as spare capacity.", "rain"
    if pd.notna(row.Capacity) and pd.notna(row["P90 attendance"]) and row.Capacity >= 4 and row["Occupied hours"] >= 2 and row["P90 attendance"] <= row.Capacity*.5:
        return (f"90% of occupied time had {row['P90 attendance']:.0f} people or fewer.",
                f"This is a {row.Capacity:g}-seat room. Test a smaller-room option, then validate peak demand, accessibility and room purpose.", "forest")
    return (f"This room was in use for {row['Utilisation %']:.0f}% of observed time.",
            "Compare the busiest periods and attendance with a similar room before changing capacity or adding equipment.", "rain")


def opportunity_counts(ctx):
    return {kind: int(ctx["issues"].loc[ctx["issues"].Kind.eq(kind), "Room key"].nunique()) for kind in ["fit", "warm", "light"]}


def next_step(text):
    st.html(f'<div class="next-step"><strong>Next decision</strong> · {escape(text)}</div>')


def feedback_in_scope(ctx, room=None, audience="Everyone"):
    from workplace.feedback_view import generated_feedback
    from workplace.feedback import filter_feedback
    records = generated_feedback(ctx["all_data"], ctx["fetched"])
    return filter_feedback(records, [room] if room else ctx["inventory"]["Room key"], ctx["start"], ctx["end"], ctx["office"], audience)


def experience_bridge(ctx, room=None):
    from workplace.feedback import feedback_summary
    s = feedback_summary(feedback_in_scope(ctx, room))
    with st.container(key="panel_experience_bridge"):
        st.html('<span class="source-tag sample">Sample sentiment · demonstration</span>')
        st.subheader("Does the experience support the decision?")
        left,right=st.columns([1,2])
        with left:
            stat("Enjoyed the space", u.fmt(s["positive"], "%", 1), f"{s['responses']} invented responses · rated 4–5", "purple")
        with right:
            st.write("Use room observations to see what happens, then ask employees and guests how it feels. A real pilot can measure both before and after a change.")
            if room:
                if st.button("View feedback for this room",key="experience_for_room",icon=":material/arrow_forward:"):
                    st.session_state["room_filter"]=[room]
                    st.switch_page("pages/Feedback.py")
            else:
                st.page_link("pages/Feedback.py",label="Explore the experience demo",icon=":material/arrow_forward:")
        st.caption("These sample opinions illustrate the future workflow. They do not validate a room change or demonstrate a return on investment.")
