"""Compact recorded environmental evidence for the four-screen story."""
from html import escape
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from workplace import ui as u, visuals as v
from workplace.pilot import pilot_plan


def environment(ctx, case):
    from workplace.briefing import html, room_picker, heading, metrics, action_signal, takeaway
    room = room_picker(ctx)
    row = ctx["inventory"].set_index("Room key").loc[room]
    stats = ctx["stats"].set_index("Room key").loc[room]
    reporting = row["Device Status"] in ("Online", "Unreported")
    source = "Sample telemetry" if ctx["demo"] else "Recorded sensor data"
    metrics([
        ("Temperature", u.fmt(row.Temperature if reporting else float("nan"), "°C", 1), "Latest selected record", source, "forest", False),
        ("Relative humidity", u.fmt(row.Humidity if reporting else float("nan"), "%", 1), "Latest selected record", source, "rain", False),
        ("Air indicator · VOC", u.fmt(row.VOC if reporting else float("nan"), digits=0), "Source units · confirm interpretation", source + " · not CO₂", "purple", False),
        ("Light level", u.fmt(row["Light Level"] if reporting else float("nan"), " lux"), "Latest selected record", source, "sunrise", False),
    ])
    st.caption(f"Latest selected record: {row.Timestamp:%d %b %Y, %H:%M} · source clock · {row['Device Status']}. These are recorded conditions, not a live comfort guarantee.")
    left, right = st.columns([1.65, 1], gap="medium")
    with left, st.container(key="brief_panel_conditions"):
        heading("See how the room conditions change", "Hourly time-weighted readings · gaps remain unknown")
        samples = ctx["samples"][ctx["samples"]["Room key"].eq(room)]
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=.09)
        for index, (signal, unit, colour) in enumerate([
            ("Temperature", "°C", "#638C7D"), ("Humidity", "% RH", "#93ABB3"), ("VOC", "Source units", "#5F259F")], 1):
            series = v.hourly_sensor(samples, signal, ctx["start"], ctx["end"], ctx["office"])
            series = series.reindex(pd.date_range(ctx["start"].floor("h"), ctx["end"].floor("h"), freq="h"))
            fig.add_trace(go.Scatter(x=series.index, y=series, mode="lines", connectgaps=False,
                                    name=signal, line=dict(color=colour, width=2.5),
                                    hovertemplate=f"%{{x|%d %b %H:%M}}<br>%{{y:.1f}} {unit}<extra>{signal}</extra>"), row=index, col=1)
            fig.update_yaxes(title_text=signal + " · " + unit, row=index, col=1)
            if not series.notna().any():
                fig.add_annotation(text="No valid readings", x=.5, y=.5, xref=f"x{index if index > 1 else ''} domain",
                                   yref=f"y{index if index > 1 else ''} domain", showarrow=False)
        u.plot_style(fig, 370)
        fig.update_layout(showlegend=False, margin=dict(l=5, r=5, t=10, b=10))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="brief_environment_trends")
    with right, st.container(key="brief_panel_environment_answer"):
        heading("What should we investigate?")
        signal = action_signal(ctx, room, "warm")
        if signal:
            html(f'<div class="brief-label">WARM WHILE RECORDED EMPTY</div><div class="brief-evidence-number">{signal["Evidence hours"]:.1f}<small> hours</small></div>')
            st.write(f"Above the {ctx['thresholds']['warm']:g}°C investigation setting during qualifying empty-room observations.")
            st.caption("Check the actual controls and schedule. Temperature alone does not prove heating was on or energy was wasted.")
        else:
            st.write("No repeated warm-empty finding meets the evidence settings in this scope.")
            st.caption("That does not establish that every condition was comfortable. Check the recordings and real user feedback together.")
        html(f'<div class="brief-owner"><b>Room use</b><span>{u.fmt(stats["Utilisation %"], "%", 1)} of observed time</span></div>')
        plan = pilot_plan(ctx, room)
        html(f'<div class="brief-insight"><b>Next step: {escape(plan["title"])}.</b>{escape(plan["gate"])} {escape(plan["measure"])}</div>')
        st.caption("VOC units must be confirmed before assigning an air-quality threshold. It is not a CO₂ reading or health score.")
    with ctx["tools"].expander("Environmental detail and room fit"):
        st.write("No comfort or air-quality pass/fail is inferred from these charts. Review levels are investigation settings, not universal standards. Sensor readings from offline devices are excluded from the trends.")
        st.page_link("pages/Spaces.py", label="Compare room size and demand", icon=":material/meeting_room:")
    takeaway("Combine the conditions with the human experience.", "Prioritise a practical check, then measure conditions and real feedback before and after a change.")
