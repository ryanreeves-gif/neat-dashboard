from __future__ import annotations

from hashlib import sha256
from html import escape
from math import ceil

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from workplace import analytics as a, ui as u, visuals as v
from workplace.scenarios import ASSUMPTIONS, attendance_bands, evaluate_layout, export_comparison, room_evidence
from workplace.views import choose_room, csv_download
from workplace.peer_view import automatic_peer


CSS = """<style>
.scenario-observed{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;background:#EAF0ED;padding:18px 22px;border-radius:16px;margin:12px 0 22px}
.scenario-observed strong{display:block;font-size:27px;line-height:1.25}
.scenario-observed span{font-size:12px;color:#4C515C}
.scenario-result{border-radius:16px;padding:22px;background:#EBF0F5;border-top:4px solid #6A87D0;min-height:380px}
.scenario-result.option-a{background:#F1ECF7;border-color:#7757A0}
.scenario-result.option-b{background:#F6F0E1;border-color:#A77E33}
.scenario-kicker{font-size:11px;letter-spacing:1px;color:#4C515C;font-weight:700}
.scenario-result h3{font-size:22px;margin:5px 0 16px;padding:0}
.scenario-layout{display:flex;gap:8px;height:75px;margin:10px 0 18px}
.scenario-room{border:2px solid #BCCADB;background:#FFFFFFB8;border-radius:13px;flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center}
.scenario-room strong{font-size:25px;line-height:1.15}.scenario-room span{font-size:11px;color:#4C515C}
.scenario-score{font-size:43px;letter-spacing:-1px;font-weight:700;line-height:1.1;margin:4px 0}
.scenario-description{font-size:12px;color:#4C515C;line-height:1.45}
.scenario-bar{height:10px;border-radius:6px;background:#D9DBE1;margin:14px 0 10px;overflow:hidden}
.scenario-bar div{height:100%;background:#557BC2}.option-a .scenario-bar div{background:#7757A0}.option-b .scenario-bar div{background:#A77E33}
.scenario-detail{display:flex;justify-content:space-between;gap:10px;font-size:12px;line-height:1.5;padding-top:9px}
.scenario-cost{border-top:1px solid #CCD2DA;margin-top:16px;padding-top:12px;font-size:14px}
@media(max-width:700px){.scenario-observed{grid-template-columns:repeat(2,1fr)}.scenario-result{min-height:0}}
</style>"""


def number(value, suffix="", digits=0):
    return "Unknown" if value is None or pd.isna(value) else f"{value:,.{digits}f}{suffix}"


def option_controls(label, token, default_seats, split_default, currency):
    st.markdown(f"**{label}**")
    split = st.checkbox("Create two rooms", **u.field_state(f"scenario_{token}_split", split_default))
    cols = st.columns(2) if split else [st.container()]
    with cols[0]:
        first = st.number_input("Room 1 seats" if split else "Seats", min_value=1, step=1,
                                **u.field_state(f"scenario_{token}_first", default_seats[0]))
    capacities = [int(first)]
    if split:
        with cols[1]:
            second = st.number_input("Room 2 seats", min_value=1, step=1,
                                     **u.field_state(f"scenario_{token}_second", default_seats[1]))
        capacities.append(int(second))
    cost = st.number_input(f"Estimated project cost ({currency})", min_value=0.0, step=500.0,
                           value=None, placeholder="Not assessed",
                           help="Enter the whole project cost, including fit-out, AV and installation. Blank means unknown.",
                           **u.field_state(f"scenario_{token}_cost_{currency}", None))
    return capacities, cost


def result_card(label, result, baseline, colour, currency, occupied_hours):
    rooms = "".join(f'<div class="scenario-room"><strong>{n}</strong><span>seats / room {i+1}</span></div>'
                    for i, n in enumerate(result["capacities"]))
    fit = result["fit_percent"]
    width = max(0, min(100, fit)) if fit is not None else 0
    exceeds = number(result["exceeds_hours"], " h", 1)
    change = result["total_seats"] - baseline["total_seats"]
    cost = ("No layout-change project" if label == "Current" else
            "Cost not assessed" if result["project_cost"] is None else f"{currency} {result['project_cost']:,.0f} entered estimate")
    st.html(f'''<article class="scenario-result {colour}">
      <div class="scenario-kicker">{'RECORDED CAPACITY' if label == 'Current' else 'YOUR SCENARIO'}</div>
      <h3>{escape(label)}</h3><div class="scenario-layout">{rooms}</div>
      <div class="scenario-score">{number(fit, '%', 1)}</div>
      <div class="scenario-description">of observed occupied time fits in one room</div>
      <div class="scenario-bar"><div style="width:{width:.4f}%"></div></div>
      <div class="scenario-detail"><span>Above largest room capacity</span><strong>{exceeds}</strong></div>
      <div class="scenario-detail"><span>Total seats</span><strong>{result['total_seats']} ({change:+d})</strong></div>
      <div class="scenario-cost">{escape(cost)}</div>
      <div class="scenario-description">{occupied_hours:.1f} occupied hours evaluated</div>
    </article>''')


def scenarios():
    u.shell("Scenarios", "Explore a different room mix.", "Compare today's room with two possible layouts, using the same observed attendance.")
    v.styles()
    st.html(CSS)
    ctx = u.context(show_evidence=False)
    room = choose_room(ctx, "Room to model")
    row = ctx["stats"].set_index("Room key").loc[room]
    capacity = row.Capacity
    if pd.isna(capacity) or capacity < 1 or int(capacity) != capacity:
        st.info("This room needs a recorded positive whole-number capacity before it can be compared. Update the room metadata or choose another room.")
        u.footer()
        return
    capacity = int(capacity)
    automatic_peer(ctx, room)
    evidence = room_evidence(ctx["samples"], room, a.window_hours(ctx["start"], ctx["end"], ctx["office"]))
    st.html('<div class="scenario-observed">' + "".join(
        f'<div><strong>{number(value, suffix, digits)}</strong><span>{label}</span></div>' for value, suffix, digits, label in [
            (evidence["typical"], "", 1, "Typical people, while occupied"),
            (evidence["p90"], "", 0, "People or fewer for 90% of occupied time"),
            (evidence["peak"], "", 0, "Highest observed people count"),
            (evidence["coverage"], "%", 1, "Coverage for this room"),
        ]) + '</div>')
    if evidence["coverage"] is None or evidence["coverage"] < 70:
        st.warning("Limited coverage for this room. Compare the recorded periods only; gather more evidence before deciding on a layout.")
    if evidence["occupied_hours"] == 0:
        st.info("No valid occupied observations in this period. You can sketch layouts and costs, but capacity fit remains unknown.")
    elif evidence["peak"] > capacity:
        st.warning("Some people counts exceed the recorded capacity. Check room metadata and sensor counts before relying on the comparison.")

    token = sha256(room.encode()).hexdigest()[:12]
    with st.expander("Edit proposed layouts and costs", expanded=False):
        st.caption("Starting layouts are examples you can edit. This comparison does not establish whether the rooms could physically be built.")
        currency = st.selectbox("Cost currency", ["GBP", "EUR", "NOK"], **u.field_state("scenario_currency", "GBP"))
        left, right = st.columns(2, gap="large")
        defaults = (max(1, ceil(capacity / 2)), max(1, capacity // 2))
        with left:
            first, cost_a = option_controls("Option A", token + "_a", defaults, False, currency)
        with right:
            second, cost_b = option_controls("Option B", token + "_b", defaults, capacity >= 2, currency)

    baseline = evaluate_layout(evidence, [capacity], 0.0)
    layouts = [("Current", baseline), ("Option A", evaluate_layout(evidence, first, cost_a)),
               ("Option B", evaluate_layout(evidence, second, cost_b))]
    st.subheader("How much of the observed attendance would fit?")
    st.caption("Every recorded count is treated as one group. For a two-room option, the group must fit in one of the rooms.")
    for column, (label, result), colour in zip(st.columns(3, gap="medium"), layouts, ["current", "option-a", "option-b"]):
        with column:
            result_card(label, result, baseline, colour, currency, evidence["occupied_hours"])
    st.caption("Fit is a share of observed occupied time, not a percentage of meetings or a prediction of future use. A second room's additional demand is not measured.")

    with st.container(key="panel_scenario_attendance"):
        st.subheader("The attendance behind the comparison")
        if evidence["occupied_hours"] > 0:
            bands = attendance_bands(evidence)
            fig = go.Figure(go.Bar(x=bands.people, y=bands.percent, marker_color=v.BLUE,
                text=[f"{p:.1f}%" for p in bands.percent], textposition="outside", cliponaxis=False,
                customdata=bands.hours, hovertemplate="%{x} people<br>%{y:.1f}% of occupied time<br>%{customdata:.2f} observed hours<extra></extra>"))
            u.plot_style(fig, 280)
            fig.update_yaxes(title="Share of occupied time (%)", range=[0, max(10, bands.percent.max()*1.2)])
            fig.update_xaxes(title="Observed people count")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="scenario_attendance")
        st.caption(f"{evidence['occupied_hours']:.1f} occupied hours evaluated. {evidence['empty_hours']:.1f} observed empty hours and {evidence['unknown_hours']:.1f} unknown hours excluded from fit.")

    with st.expander("Assumptions and what to check before a change"):
        for assumption in ASSUMPTIONS:
            st.write("• " + assumption)
        st.caption("Options are remembered per room during this session. Currency changes select a separate entered cost; no conversion is performed.")
    csv_download(export_comparison(ctx, room, evidence, layouts, currency),
                 "Download scenario comparison", "neat-room-scenarios.csv", "scenario_export")
    st.caption("Download includes the selected room, dates, hours, costs, coverage and assumptions. No changes are made to room settings.")
    u.footer()
