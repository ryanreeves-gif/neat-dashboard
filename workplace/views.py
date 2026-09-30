from __future__ import annotations
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from workplace import analytics as a
from workplace import ui as u

SIGNALS = {"Occupancy": "People", "Temperature": "°C", "Humidity": "% RH", "Light Level": "lux", "VOC": "Source units"}


def chart(fig, key):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "scrollZoom": False}, key=key)


def csv_download(frame, label, name, key):
    out = frame.copy()
    for c in out.select_dtypes(include=["object", "string"]).columns:
        out[c] = out[c].map(lambda v: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v)
    st.download_button(label, out.to_csv(index=False).encode("utf-8-sig"), name, "text/csv", key=key)


def finding_rows(issues, prefix, limit=None):
    if issues.empty:
        st.write("No findings meet the current evidence thresholds.")
        st.caption("Check observation coverage and the selected period before drawing a conclusion.")
        return
    show = issues.head(limit) if limit else issues
    for i, row in show.reset_index(drop=True).iterrows():
        c1, c2, c3, c4 = st.columns([1.4, 2.4, 2.4, .8], vertical_alignment="center")
        with c1:
            st.write(f"**{row['Room']}**")
            st.caption(row.Location)
        with c2:
            st.write(row.Finding)
            st.caption(row.Evidence)
        with c3:
            st.write(row["Next step"])
            st.caption(f"Suggested owner: {row.Owner}")
        with c4:
            if st.button("Evidence", key=f"evidence_{prefix}_{i}", help=f"Open observations for {row['Room']}"):
                u.go_room(row["Room key"])
        if i < len(show) - 1:
            st.divider()


def report(ctx):
    s = ctx["summary"]
    lines = ["NEAT | WORKPLACE BRIEF", f"Scope: {ctx['start']:%d %b %Y} – {ctx['end']:%d %b %Y %H:%M} (recorded source time)",
             "Locations: " + ", ".join(sorted(ctx["inventory"].Location.unique())),
             f"Rooms monitored: {s['rooms']}", f"Space utilisation: {u.fmt(s['utilisation'], '%')}",
             f"Typical attendance when occupied: {u.fmt(s['attendance'], digits=1)} people",
             f"Occupancy coverage: {u.fmt(s['coverage'], '%')}", "", "WHERE TO FOCUS"]
    for _, r in ctx["issues"].drop_duplicates("Room key").head(3).iterrows():
        lines += [f"{r['Room key']}: {r.Finding}", f"Evidence: {r.Evidence}", f"Next step: {r['Next step']}", ""]
    lines += ["METHOD", "Utilisation = occupied observed room-hours / valid observed room-hours.",
              "Attendance = observed person-hours / occupied room-hours. Unknown and offline occupancy is excluded.",
              "Observations are time-weighted and capped at room sampling cadence. Gaps are not treated as empty.",
              "Office hours = weekdays 08:00–19:00 in the source clock." if ctx["office"] else "All hours selected.",
              f"Investigation settings: >{ctx['thresholds']['warm']:g} °C or >{ctx['thresholds']['bright']:g} lux while empty; at least {ctx['thresholds']['minimum']:g} hours.",
              "Findings require investigation. Bookings, building controls and energy meters are not connected."]
    if st.session_state.get("demo_mode"):
        lines.insert(1, "DEMONSTRATION — GENERATED SAMPLE DATA")
    return "\n".join(lines)


def overview():
    u.shell("Overview", "Your workplace. Understood.", "See how your spaces work. Know where to focus next.")
    ctx = u.context()
    s, previous = ctx["summary"], ctx["previous"]
    delta = None
    if s["coverage"] >= 70 and previous["coverage"] >= 70 and pd.notna(previous["utilisation"]):
        delta = f"{s['utilisation'] - previous['utilisation']:+.0f} percentage points vs previous period"
    cols = st.columns(4, gap="medium")
    with cols[0]: u.metric("Rooms monitored", str(s["rooms"]), "In your selected scope", "rooms", "rooms")
    with cols[1]: u.metric("Space utilisation", u.fmt(s["utilisation"], "%"), "Of valid observed room-hours", "utilisation", "util", delta)
    with cols[2]: u.metric("Typical attendance", u.fmt(s["attendance"], digits=1), "People, while rooms are occupied", "attendance", "attendance")
    with cols[3]: u.metric("Rooms to review", str(ctx["issues"]["Room key"].nunique()), "With evidence worth investigating", "reviews", "reviews")
    st.write("")
    left, right = st.columns([1.55, 1], gap="medium")
    with left, st.container(key="panel_heatmap"):
        u.section("When are rooms busiest?", "heatmap")
        days, bands, z, observed = a.heatmap(ctx["samples"], ctx["office"])
        labels = np.array([["—" if np.isnan(v) else f"{v:.0f}%" for v in row] for row in z])
        fig = go.Figure(go.Heatmap(x=days, y=bands, z=z, customdata=observed, text=labels,
            texttemplate="%{text}", textfont={"size": 14}, colorscale=[[0, "#F0F3F8"], [.5, "#B9C9EC"], [1, u.BLUE]],
            zmin=0, zmax=100, showscale=False, xgap=7, ygap=7, hoverongaps=False,
            hovertemplate="%{x} · %{y}<br>%{z:.1f}% occupied<br>%{customdata:.1f} observed room-hours<extra></extra>"))
        u.plot_style(fig, 238)
        fig.update_yaxes(autorange="reversed", showgrid=False)
        chart(fig, "demand_heatmap")
        st.caption("Light → dark: 0–100% occupied · gaps: no valid observations")
    with right, st.container(key="panel_fit"):
        u.section("Does the room fit?", "fit")
        fit = ctx["issues"].query("Kind == 'fit'")
        candidates = ctx["stats"].query("Capacity > 0 and `Occupied hours` > 0")
        if candidates.empty:
            st.write("More occupied observations and room capacity metadata are needed.")
        else:
            r = candidates[candidates["Room key"] == fit.iloc[0]["Room key"]].iloc[0] if not fit.empty else candidates.sort_values("Occupied hours", ascending=False).iloc[0]
            st.write(f"**{r['Room Name']}**")
            st.caption(r.Location)
            st.html(f'<div class="roomfit"><div><div class="roomfit-number">{u.fmt(r["Typical attendance"], digits=1)}</div><div class="roomfit-caption">typical people</div></div><div><div class="roomfit-number">{u.fmt(r.Capacity)}</div><div class="roomfit-caption">available seats</div></div></div>')
            st.write(f"90% of observed occupied time: **{u.fmt(r['P90 attendance'])} people or fewer**.")
            st.caption("Review the room mix against peak demand." if not fit.empty else "An example from the most-used rooms in this scope.")
            if st.button("Explore this room", key="fit_room", type="primary"):
                u.go_room(r["Room key"])
    st.write("")
    with st.container(key="panel_focus"):
        u.section("Where to focus", "focus")
        st.caption("Three rooms to start with · ranked by observed evidence hours")
        finding_rows(ctx["issues"].drop_duplicates("Room key"), "overview", 3)
        c1, c2 = st.columns([1, 1])
        with c1: st.page_link("pages/Insights.py", label="View all findings", icon=":material/arrow_forward:")
        with c2: st.download_button("Download workplace brief", report(ctx), "neat-workplace-brief.txt", "text/plain")
    u.footer()


def room_trend(ctx, room_key, signal, key):
    raw = ctx["data"]
    r = raw[(raw["Room key"] == room_key) & raw.Timestamp.between(ctx["start"], ctx["end"])].copy()
    if signal == "Occupancy":
        seg = ctx["samples"][ctx["samples"]["Room key"] == room_key]
        x, y = [], []
        for _, row in seg.iterrows():
            value = row.Occupancy if row["Valid hours"] > 0 else None
            x.extend([row.Start, row.End, None]); y.extend([value, value, None])
        fig = go.Figure(go.Scatter(x=x, y=y, mode="lines", line={"color": u.BLUE, "width": 2}, name="Observed people", connectgaps=False))
        st.caption("Time-weighted observation intervals · gaps are unknown")
    else:
        if ctx["office"]:
            r = r[(r.Timestamp.dt.dayofweek < 5) & r.Timestamp.dt.hour.between(8, 18)]
        r.loc[~r["Device Status"].isin(["Online", "Unreported"]), signal] = np.nan
        series = r.set_index("Timestamp")[signal].resample("h").mean()
        if not series.notna().any():
            st.info("No valid readings for this signal in the selected scope.")
            return
        fig = go.Figure(go.Scatter(x=series.index, y=series, mode="lines+markers", marker={"size": 3}, line={"color": u.BLUE, "width": 2}, connectgaps=False, name=signal))
        st.caption("Hourly reading averages · gaps are unknown")
    fig.update_yaxes(title=SIGNALS[signal], rangemode="tozero" if signal == "Occupancy" else "normal")
    chart(u.plot_style(fig, 310), key)


def choose_room(ctx, label="Room"):
    opts = sorted(ctx["inventory"]["Room key"])
    if st.session_state.get("selected_room") not in opts:
        st.session_state["selected_room"] = opts[0]
    return st.selectbox(label, opts, **u.field_state("selected_room", opts[0]))


def spaces():
    u.shell("Spaces", "A better fit for every room.", "Separate how often a room is used from how well its size meets demand.")
    ctx = u.context()
    room = choose_room(ctx)
    r = ctx["stats"].set_index("Room key").loc[room]
    c = st.columns(4)
    with c[0]: u.metric("Space utilisation", u.fmt(r["Utilisation %"], "%"), "Of observed room-hours", "utilisation", "space_util")
    with c[1]: u.metric("Typical attendance", u.fmt(r["Typical attendance"], digits=1), "People, when occupied", "attendance", "space_att")
    with c[2]: u.metric("Recorded capacity", u.fmt(r.Capacity), "Seats from source metadata", "fit", "space_cap")
    with c[3]: u.metric("Observation coverage", u.fmt(r["Coverage %"], "%"), "Of selected operating hours", "coverage", "space_cov")
    with st.container(key="panel_history"):
        u.section("The evidence over time", "trend")
        signal = st.selectbox("Signal", list(SIGNALS), key="room_signal")
        room_trend(ctx, room, signal, "room_history")
    with st.container(key="panel_room_findings"):
        u.section("Findings for this room", "focus", "room")
        found = ctx["issues"][ctx["issues"]["Room key"] == room]
        if found.empty: st.write("No findings meet the current evidence thresholds.")
        for _, f in found.iterrows():
            st.write(f"**{f.Finding}** — {f.Evidence}")
            st.caption(f"Why it matters: {f['Why it matters']} Next step: {f['Next step']}.")
    with st.container(key="panel_room_comparison"):
        u.section("Compare your spaces", "fit", "comparison")
        columns = ["Room Name", "Location", "Capacity", "Utilisation %", "Typical attendance", "P90 attendance", "Occupied hours", "Coverage %"]
        st.dataframe(ctx["stats"][columns].round(1), hide_index=True, width="stretch")
        csv_download(ctx["stats"][columns], "Download room comparison", "neat-room-comparison.csv", "room_comparison_csv")
        raw = ctx["data"][(ctx["data"]["Room key"] == room) & ctx["data"].Timestamp.between(ctx["start"], ctx["end"])]
        csv_download(raw, "Download source observations for this room", "neat-room-observations.csv", "room_source_csv")
    u.footer()


def environment():
    u.shell("Environment", "Make every space feel better.", "Understand room conditions and investigate recurring signals.")
    ctx = u.context()
    room = choose_room(ctx)
    with st.container(key="panel_environment"):
        u.section("Room conditions", "environment")
        signal = st.selectbox("Environmental signal", ["Temperature", "Humidity", "Light Level", "VOC"], key="environment_signal")
        seg = ctx["samples"][ctx["samples"]["Room key"] == room]
        valid = seg[signal].notna() & seg["Device Status"].isin(["Online", "Unreported"])
        hours = seg.loc[valid, "Hours"].sum()
        scheduled = a.window_hours(ctx["start"], ctx["end"], ctx["office"])
        st.caption(f"{signal} observation coverage: {u.fmt(100 * hours / scheduled if scheduled else np.nan, '%')} · {hours:.1f} observed hours")
        room_trend(ctx, room, signal, "environment_history")
        if signal == "VOC": st.caption("VOC is shown in source units. Confirm the collector's concentration field before labelling this ppb; it is not VOC Index or measured CO₂.")
    with st.container(key="panel_environment_findings"):
        u.section("Conditions to investigate", "focus", "environment")
        st.caption("Across the selected scope · warmth and brightness alone do not establish energy use")
        finding_rows(ctx["issues"][ctx["issues"].Kind.isin(["warm", "light"])], "environment", 10)
    u.footer()


def insights():
    u.shell("Insights", "Evidence. Then action.", "Prioritise the next conversation with facilities and workplace teams.")
    ctx = u.context()
    with st.container(key="panel_insights"):
        u.section("All findings", "focus", "insights")
        labels = {"All findings": None, "Room fit": "fit", "Warm while empty": "warm", "Bright while empty": "light"}
        choice = st.selectbox("Finding type", list(labels))
        issues = ctx["issues"]
        if labels[choice]: issues = issues[issues.Kind == labels[choice]]
        st.caption(f"{len(issues)} findings · ordered by qualifying observed hours; this is not a financial ranking")
        finding_rows(issues, "insights")
        csv_download(issues.drop(columns=["Rank", "Kind"]), "Download evidence and next steps", "neat-findings.csv", "insights_csv")
    with st.expander("What would strengthen the business case?"):
        st.write("**Bookings** establish whether an empty room was actually reserved. **Building controls** establish whether HVAC or lighting was operating. **Energy meters and an agreed baseline** support measured savings. Link those sources to the same room identifier and timestamps before reporting no-shows or financial outcomes.")
    u.footer()


def operations():
    u.shell("Operations", "Keep the workplace ready.", "Review the latest recorded room state and prepare evidence for a handoff.")
    ctx = u.context()
    inv = ctx["inventory"]
    with st.container(key="panel_fleet"):
        u.section("Latest recorded room state", "fleet")
        st.caption("One latest record per named room · timestamps reflect the selected date range")
        columns = ["Room Name", "Location", "Device Status", "Platform", "Software Version", "Timestamp"]
        st.dataframe(inv[columns].sort_values(["Device Status", "Room Name"]), hide_index=True, width="stretch")
        st.dataframe(inv.Platform.value_counts().rename_axis("Platform").reset_index(name="Rooms"), hide_index=True, width="stretch")
        csv_download(inv[columns], "Download room state", "neat-room-state.csv", "fleet_csv")
    with st.container(key="panel_workflow"):
        u.section("Preview a facilities handoff", "workflow")
        st.caption("Draft export only · no ticket, device command or building control is sent")
        issues = ctx["issues"]
        if issues.empty: st.write("A qualifying finding will make an evidence-backed handoff available here.")
        else:
            idx = st.selectbox("Finding to include", list(issues.index), format_func=lambda i: f"{issues.loc[i, 'Room key']} · {issues.loc[i, 'Finding']}")
            r = issues.loc[idx]
            payload = {"status": "draft_not_sent", "demonstration_data": bool(st.session_state.get("demo_mode")),
                       "room": r["Room key"], "finding": r.Finding, "evidence": r.Evidence,
                       "period_start": ctx["start"].isoformat(), "period_end": ctx["end"].isoformat(),
                       "clock": "recorded_source_time", "operating_hours": "weekdays_08_19" if ctx["office"] else "all_hours",
                       "evidence_hours": float(r["Evidence hours"]), "investigation_thresholds": ctx["thresholds"],
                       "suggested_owner": r.Owner, "proposed_next_step": r["Next step"], "confirmed_energy_savings": None}
            st.json(payload, expanded=False)
            st.download_button("Download draft handoff", json.dumps(payload, indent=2), "neat-handoff-draft.json", "application/json")
    u.footer()


def ask():
    u.shell("Ask the data", "Start with a useful question.", "Clear answers grounded in the observations you have selected.")
    ctx = u.context()
    with st.container(key="panel_ask"):
        u.section("Explore a question", "ask")
        question = st.selectbox("What would you like to understand?", ["Where should we focus first?", "Which rooms may be oversized?", "Where should facilities investigate?", "Which rooms were last reported offline?", "How much of the period did we observe?"])
        if question == "Where should we focus first?": finding_rows(ctx["issues"].drop_duplicates("Room key"), "ask_priority", 3)
        elif question == "Which rooms may be oversized?": finding_rows(ctx["issues"][ctx["issues"].Kind.eq("fit")], "ask_fit")
        elif question == "Where should facilities investigate?": finding_rows(ctx["issues"][ctx["issues"].Kind.isin(["warm", "light"])], "ask_facilities")
        elif question == "Which rooms were last reported offline?":
            offline = ctx["inventory"][ctx["inventory"]["Device Status"].eq("Offline")]
            if offline.empty: st.write("No rooms were reported offline in their latest selected record.")
            else: st.dataframe(offline[["Room Name", "Location", "Timestamp", "Device Status"]], hide_index=True, width="stretch")
            st.caption("Unknown states are not counted as online. Review Operations for the full snapshot.")
        else:
            s = ctx["summary"]
            st.write(f"**{u.fmt(s['coverage'], '%')}** occupancy observation coverage: {s['valid_hours']:,.1f} valid room-hours out of {s['expected_hours']:,.1f} scheduled room-hours.")
            st.write("Missing samples, missing occupancy and offline or unknown device states reduce coverage. They do not become empty-room time.")
            st.dataframe(ctx["stats"][["Room Name", "Location", "Observed hours", "Coverage %"]].round(1), hide_index=True, width="stretch")
    u.footer()
