from __future__ import annotations
import json
import time
from html import escape
from datetime import datetime, timezone
from uuid import uuid4
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from workplace import analytics as a
from workplace import ui as u
from workplace import visuals as v
from workplace import customer as c
from workplace.executive import decision_actions
from workplace.brief import pdf_brief

SIGNALS = {"Occupancy": "People", "Temperature": "\xb0C", "Humidity": "% RH", "Light Level": "lux", "VOC": "Source units"}


def chart(fig, key):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "scrollZoom": False}, key=key)


def csv_download(frame, label, name, key):
    out = frame.copy()
    for c in out.select_dtypes(include=["object", "string"]).columns:
        out[c] = out[c].map(lambda v: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v)
    st.download_button(label, out.to_csv(index=False).encode("utf-8-sig"), name, "text/csv", key=key)


def focus_environment(room_key, kind):
    st.session_state["selected_room"] = room_key
    st.session_state["environment_signal"] = "Light Level" if kind == "light" else "Temperature"
    st.session_state["environment_action"] = "lights" if kind == "light" else "eco"
    st.session_state["environment_action_room"] = room_key


def finding_rows(issues, prefix, limit=None, environment_evidence=False, show_room=True):
    if issues.empty:
        st.write("No findings meet the current evidence thresholds.")
        return
    show = issues.head(limit) if limit else issues
    st.caption("Bar lengths compare observed evidence hours across these cards.")
    largest = show["Evidence hours"].max()
    rows = show.reset_index(drop=True)
    for start in range(0, len(rows), 3):
        columns = st.columns(min(3, len(rows) - start), gap="medium")
        for column, (i, row) in zip(columns, rows.iloc[start:start+3].iterrows()):
            with column, st.container(key=f"finding_{prefix}_{i}"):
                v.finding_summary(row, largest, show_room)
                with st.expander("Details and next step"):
                    st.write(row.Evidence)
                    st.caption(row["Why it matters"])
                    st.write(f"**Next step:** {row['Next step']}")
                    st.caption(f"Owner: {row.Owner}")
                if environment_evidence:
                    st.button("Evidence", key=f"evidence_{prefix}_{i}", width="stretch",
                              help=f"Show conditions and suggested actions for {row['Room']}",
                              on_click=focus_environment, args=(row["Room key"], row.Kind))
                elif show_room and st.button("Evidence", key=f"evidence_{prefix}_{i}", width="stretch",
                                             help=f"Open observations for {row['Room']}"):
                    u.go_room(row["Room key"])


def report(ctx):
    s = ctx["summary"]
    lines = ["NEAT | WORKPLACE BRIEF", f"Scope: {ctx['start']:%d %b %Y} \u2013 {ctx['end']:%d %b %Y %H:%M} (recorded source time)",
             "Locations: " + ", ".join(sorted(ctx["inventory"].Location.unique())),
             f"Rooms monitored: {s['rooms']}", f"Space utilisation: {u.fmt(s['utilisation'], '%')}",
             f"Typical attendance when occupied: {u.fmt(s['attendance'], digits=1)} people",
             f"Occupancy coverage: {u.fmt(s['coverage'], '%')}", "", "WHERE TO FOCUS"]
    for _, r in ctx["issues"].drop_duplicates("Room key").head(3).iterrows():
        lines += [f"{r['Room key']}: {r.Finding}", f"Evidence: {r.Evidence}", f"Next step: {r['Next step']}", ""]
    lines += ["METHOD", "Utilisation = occupied observed room-hours / valid observed room-hours.",
              "Attendance = observed person-hours / occupied room-hours. Unknown and offline occupancy is excluded.",
              "Observations are time-weighted and capped at room sampling cadence. Gaps are not treated as empty.",
              "Office hours = weekdays 08:00\u201319:00 in the source clock." if ctx["office"] else "All hours selected.",
              f"Investigation settings: >{ctx['thresholds']['warm']:g} \xb0C or >{ctx['thresholds']['bright']:g} lux while empty; at least {ctx['thresholds']['minimum']:g} hours.",
              "Findings require investigation. Bookings, building controls and energy meters are not connected."]
    if st.session_state.get("demo_mode"):
        lines.insert(1, "DEMONSTRATION \u2014 GENERATED SAMPLE DATA")
    return "\n".join(lines)


def executive_panel(ctx):
    with st.container(key="panel_decisions"):
        u.section("Your next moves", "focus")
        st.caption("Start with these priorities, then measure the effect on cost, use and real user feedback.")
        actions = decision_actions(ctx)
        columns = st.columns(len(actions), gap="medium")
        for i, (column, action) in enumerate(zip(columns, actions)):
            with column, st.container(key=f"decision_{i}"):
                coverage = "" if action["coverage"] is None else f" · {action['coverage']:.0f}% coverage"
                st.html(f'''<div class="decision-number">{i+1:02d} / INVESTIGATE</div>
                  <h3 class="decision-title">{escape(action['title'])}</h3>
                  <div class="decision-scope">{escape(action['scope'])}{escape(coverage)}</div>
                  <div class="decision-evidence">{escape(action['evidence'])}</div>
                  <div class="decision-outcome">{escape(action['benefit'])}</div>
                  <div class="decision-meta">Suggested owner: {escape(action['owner'])}</div>''')
                with st.expander("How to assess the result"):
                    st.write(action["action"])
                    st.write(action["measure"])
                    st.caption(f"Cost: {action['cost']}. Agree a baseline, target, budget and review date before a pilot.")
                if action["room_key"] and st.button("Explore evidence", key=f"decision_evidence_{i}", width="stretch"):
                    u.go_room(action["room_key"])
        st.write("")
        c1, c2 = st.columns([1, 1], vertical_alignment="center")
        with c1:
            st.page_link("pages/Insights.py", label="View all findings", icon=":material/arrow_forward:")
        with c2:
            st.download_button("Download one-page decision brief", pdf_brief(ctx), "neat-workplace-decision-brief.pdf",
                               "application/pdf", key="executive_pdf", type="primary", width="stretch")
        st.caption("PDF follows the selected evidence. Live bookings, feedback and financial outcomes are not connected.")


def overview():
    from workplace.overview_view import render
    render(executive_panel)


def room_trend(ctx, room_key, signal, key):
    if signal == "Occupancy":
        v.occupancy_pattern(ctx, room_key, key)
        return
    seg = ctx["samples"][ctx["samples"]["Room key"] == room_key]
    series = v.hourly_sensor(seg, signal, ctx["start"], ctx["end"], ctx["office"])
    series = series.reindex(pd.date_range(ctx["start"].floor("h"), ctx["end"].floor("h"), freq="h"))
    if not series.notna().any():
        st.info("No valid readings for this signal in the selected scope.")
        return
    fig = go.Figure(go.Scatter(x=series.index, y=series, mode="lines+markers", marker={"size": 6},
        line={"color": v.BLUE, "width": 3.5}, connectgaps=False, name=signal,
        hovertemplate=f"%{{x|%a %d %b, %H:%M}}<br>%{{y:.1f}} {SIGNALS[signal]}<extra></extra>"))
    if signal in ("Temperature", "Light Level"):
        threshold = ctx["thresholds"]["warm" if signal == "Temperature" else "bright"]
        fig.add_hline(y=threshold, line_width=1.5, line_dash="dash", line_color=v.AMBER,
                      annotation_text=f"Review level {threshold:g} {SIGNALS[signal]}", annotation_position="top left")
        low, high = min(series.min(), threshold), max(series.max(), threshold)
        padding = max((high-low)*.15, 1 if signal == "Temperature" else 5)
        fig.update_yaxes(range=[max(0, low-padding) if signal == "Light Level" else low-padding, high+padding])
    fig.update_yaxes(title=SIGNALS[signal])
    chart(u.plot_style(fig, 310), key)
    st.caption("Hourly time-weighted readings \xb7 gaps remain unknown")


def choose_room(ctx, label="Room"):
    opts = sorted(ctx["inventory"]["Room key"])
    if st.session_state.get("selected_room") not in opts:
        st.session_state["selected_room"] = opts[0]
    return st.selectbox(label, opts, **u.field_state("selected_room", opts[0]))


def environment_actions(ctx, room):
    """Local demonstration only: this function never calls ServiceNow or a BMS."""
    actions = {
        "eco": {
            "label": "HVAC eco mode",
            "kind": "warm",
            "checks": "Confirm current vacancy, upcoming bookings and the actual HVAC operating mode.",
            "command": "Request the room's configured HVAC standby / eco mode",
            "control_point": "the configured HVAC occupancy-mode point to the site's standby / eco value",
            "follow_up": "Check HVAC mode feedback and room conditions; restore the normal schedule when occupancy returns or the override expires.",
        },
        "temperature": {
            "label": "Adjust temperature target",
            "kind": "warm",
            "checks": "Confirm current temperature, occupancy, the existing setpoint and permitted comfort limits.",
            "command": "Request a temporary room temperature target",
            "control_point": "the configured room temperature-setpoint point to the selected target",
            "follow_up": "Check the accepted setpoint and subsequent temperature trend; an accepted command alone does not prove improved comfort.",
        },
        "lights": {
            "label": "Switch room lights off",
            "kind": "light",
            "checks": "Confirm current vacancy and bookings, actual lighting state and daylight contribution; exclude emergency lighting.",
            "command": "Request ordinary room lighting off with occupancy override enabled",
            "control_point": "the configured ordinary-lighting command point to off, retaining occupancy override",
            "follow_up": "Check lighting circuit feedback; restore normal occupancy control when someone enters or the override expires.",
        },
        "purge": {
            "label": "Air purge / ventilation boost",
            "kind": None,
            "checks": "Validate the air-quality sensor, units and threshold; confirm the ventilation system supports a suitable boost sequence.",
            "command": "Request the building's configured timed ventilation boost",
            "control_point": "the configured ventilation-boost point to the site's approved boost mode",
            "follow_up": "Check ventilation feedback and subsequent validated air-quality readings; restore the normal schedule when the boost expires.",
        },
    }
    found = ctx["issues"][(ctx["issues"]["Room key"] == room) & ctx["issues"].Kind.isin(["warm", "light"])]
    if st.session_state.get("environment_action_room") != room:
        kind = found.iloc[0].Kind if not found.empty else None
        st.session_state["environment_action"] = "lights" if kind == "light" else "eco"
        st.session_state["environment_action_room"] = room
    if st.session_state.get("environment_action") not in actions:
        st.session_state["environment_action"] = "eco"

    with st.container(key="panel_environment_actions", border=True):
        st.subheader("Suggested action")
        st.caption(f"Selected room: {room}")
        st.info("For demonstration purposes only. No settings were changed.")
        selected = st.selectbox("Action to demonstrate", list(actions),
                                format_func=lambda k: actions[k]["label"], key="environment_action")
        action = actions[selected]
        matching = found[found.Kind.eq(action["kind"])] if action["kind"] else found.iloc[:0]
        if matching.empty:
            st.write("**Manual scenario** \xb7 This action is not triggered by a qualifying finding for this room.")
        else:
            for _, f in matching.iterrows():
                st.caption(f"{f.Finding} \u00b7 {f['Evidence hours']:.1f} observed hours")
        if selected == "purge":
            st.caption("Air purge is a manual demonstration until the air-quality field, units and rule have been validated.")

        left, right = st.columns(2)
        with left:
            minutes = st.slider("Temporary override (minutes)", 5, 60, 15, 5, key="environment_duration")
        target = None
        with right:
            if selected == "temperature":
                target = st.number_input("Example temperature target (\xb0C)", 18.0, 26.0, 21.0, .5,
                                         key="environment_target")
            else:
                st.caption("Returns to the building schedule at expiry.")
        command = action["command"]
        if target is not None:
            command += f" of {target:g} \xb0C"
        command += f" for {minutes} minutes."
        st.write(f"**Proposed action:** {command}")
        with st.expander("Integration design and checks"):
            st.write(action["checks"])
            st.write("Resolve this room to the correct BMS zone and control points; apply site permissions, interlocks and override limits.")
            st.caption("ServiceNow endpoints, gateway connections, point names and permitted values would be configured for each building.")
            st.write(f"**Follow-up:** {action['follow_up']}")

        latest = ctx["inventory"].set_index("Room key").loc[room]
        snapshot = {"recorded_at": latest.Timestamp.isoformat(), "device_status": str(latest["Device Status"])}
        for column in ["Occupancy", "Temperature", "Humidity", "Light Level", "VOC"]:
            value = latest.get(column)
            snapshot[column] = float(value) if pd.notna(value) else None
        st.caption(f"Latest record in the selected period: {latest.Timestamp:%d %b %Y %H:%M} \xb7 recorded source time.")
        config = {
            "workflow_version": 2,
            "room": room,
            "action": selected,
            "action_label": action["label"],
            "duration_minutes": minutes,
            "temperature_target_c": target,
            "proposed_command": command,
            "period_start": ctx["start"].isoformat(),
            "period_end": ctx["end"].isoformat(),
            "clock": "recorded_source_time",
            "office_hours_only": bool(ctx["office"]),
            "source_fetched_at": str(ctx["fetched"]),
            "source_is_sample_data": bool(st.session_state.get("demo_mode", False)),
            "investigation_thresholds": ctx["thresholds"],
            "basis": "observed_finding" if not matching.empty else "manual_scenario",
            "findings": matching[["Finding", "Evidence"]].to_dict("records"),
            "latest_selected_record": snapshot,
        }
        signature = json.dumps(config, sort_keys=True, default=str)
        if st.button("Demonstrate suggested action" if not matching.empty else "Demonstrate scenario",
                     key="environment_run", type="primary"):
            demo_id = "DEMO-" + uuid4().hex[:8].upper()
            trigger = (
                "evaluate the selected sensor observations against the investigation thresholds and attach the matching findings"
                if not matching.empty else
                "capture the operator-selected scenario and attach the available sensor observations"
            )
            control_point = action["control_point"]
            if target is not None:
                control_point += f" of {target:g} \xb0C"
            stages = [
                ("Event source",
                 f"The Streamlit middleware would {trigger} for {room}. "
                 "The Neat Pulse reporting feed would supply the room observations, with original timestamps retained for traceability."),
                ("Middleware request",
                 "The middleware would send an authenticated HTTPS POST with a JSON payload to a configured ServiceNow REST endpoint. "
                 f"The payload would identify the room, action, {minutes}-minute duration, any temperature target, "
                 f"sensor evidence and correlation reference {demo_id}."),
                ("ServiceNow decision engine",
                 "A configured ServiceNow workflow would validate the request, match the room to its building zone and apply facilities policy. "
                 f"Checks: {action['checks']} "
                 "It would route a permitted request to the building integration, or hold it for facilities review."),
                ("BMS gateway and control",
                 "An integration connector would pass the approved request to a BMS gateway, such as Tridium Niagara. "
                 f"The gateway would map {room} to its commissioned control points and request {control_point} "
                 f"for {minutes} minutes through the configured protocol, for example BACnet. "
                 "The building controller would retain its operating limits and interlocks."),
                ("Acknowledgement and feedback",
                 f"The integration would return gateway acceptance and control-point readback to ServiceNow and the dashboard under {demo_id}. "
                 "Request acceptance, confirmed equipment state, rejection and timeout would be tracked separately."),
                ("Verify and restore",
                 "The workflow would use fresh sensor readings and controller feedback to assess the result and release the temporary override "
                 f"at expiry or the applicable occupancy trigger. Follow-up: {action['follow_up']}"),
            ]
            events = []
            with st.status("Demonstrating the facilities workflow\u2026", expanded=False) as status:
                for number, (stage, detail) in enumerate(stages, 1):
                    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    events.append({"time_utc": stamp, "stage": stage, "detail": detail})
                    st.write(f"**{number}. {stage}**")
                    st.write(detail)
                    time.sleep(.2)
                status.update(label="Workflow demonstration complete", state="complete", expanded=False)
            payload = dict(config, mode="simulation", demo_reference=demo_id, events=events,
                           service_now_ticket_id=None, command_sent=False,
                           gateway_acknowledgement=None, measured_outcome=None)
            st.session_state["environment_demo_run"] = {"signature": signature, "payload": payload}

        result = st.session_state.get("environment_demo_run")
        if result and result["signature"] == signature:
            payload = result["payload"]
            st.success(f"Demonstration complete for {room}.")
            v.workflow_map(payload["events"])
            with st.expander("Technical sequence of events", expanded=False):
                st.caption(f"Workflow reference: {payload['demo_reference']} \xb7 demonstration recorded at {payload['events'][0]['time_utc']}")
                for number, event in enumerate(payload["events"], 1):
                    st.write(f"**{number}. {event['stage']}**")
                    st.write(event["detail"])
            st.download_button("Download demonstration record", json.dumps(payload, indent=2, default=str),
                               "neat-workflow-demonstration.json", "application/json", key="environment_demo_download")


def spaces():
    from workplace.peer_view import automatic_peer
    u.shell("Spaces", "The right room for the way you work.", "Find where the room mix supports demand and where a different size may work better.")
    v.styles()
    ctx = u.context()
    room = choose_room(ctx)
    r = ctx["stats"].set_index("Room key").loc[room]
    title,detail,tone=c.room_story(r)
    c.answer(r['Room Name'] + " · the takeaway",title,detail,tone)
    cols = st.columns(4)
    with cols[0]: u.metric("Time in use", u.fmt(r["Utilisation %"], "%"), "Of observed room-hours", "utilisation", "space_util")
    with cols[1]: u.metric("Typical attendance", u.fmt(r["Typical attendance"], digits=1), "People, when occupied", "attendance", "space_att")
    with cols[2]: u.metric("Recorded capacity", u.fmt(r.Capacity), "Seats from source metadata", "fit", "space_cap")
    with cols[3]: u.metric("Observation coverage", u.fmt(r["Coverage %"], "%"), "Of selected operating hours", "coverage", "space_cov")
    with st.container(key="panel_selected_fit"):
        u.section("People and available seats", "fit", "selected_room")
        v.capacity_bar(r["Typical attendance"], r.Capacity, r["P90 attendance"])
        if st.button("Compare alternative layouts", key="room_scenarios", type="primary"):
            u.go_scenario(room)
    automatic_peer(ctx, room)
    with st.container(key="panel_history"):
        u.section("Check the peaks before changing the room", "trend")
        signal = st.selectbox("Signal", list(SIGNALS), key="room_signal")
        room_trend(ctx, room, signal, "room_history")
    c.experience_bridge(ctx,room)
    with st.container(key="panel_room_findings"):
        u.section("Findings for this room", "focus", "room")
        found = ctx["issues"][ctx["issues"]["Room key"] == room]
        finding_rows(found, "selected_room", show_room=False)
    with st.container(key="panel_room_comparison"):
        u.section("Compare your spaces", "fit", "comparison")
        columns = ["Room Name", "Location", "Capacity", "Utilisation %", "Typical attendance", "P90 attendance", "Occupied hours", "Coverage %"]
        compare = ctx["stats"].dropna(subset=["Utilisation %"]).sort_values("Utilisation %", ascending=False).head(12).iloc[::-1]
        if not compare.empty:
            fig = go.Figure(go.Bar(x=compare["Utilisation %"], y=compare["Room key"], orientation="h",
                marker_color=[v.BLUE if coverage >= 70 else "#93ABB3" for coverage in compare["Coverage %"]],
                text=[f"{value:.0f}%" for value in compare["Utilisation %"]], textposition="outside", cliponaxis=False,
                customdata=compare["Coverage %"], hovertemplate="%{y}<br>Occupied: %{x:.1f}%<br>Coverage: %{customdata:.0f}%<extra></extra>"))
            u.plot_style(fig, max(210, 42 * len(compare)))
            fig.update_xaxes(range=[0, 110], ticksuffix="%", title="Occupied share of observed time")
            fig.update_yaxes(showgrid=False)
            chart(fig, "space_comparison")
            st.caption("Up to 12 rooms, ordered by use. Grey bars have less than 70% observation coverage.")
        with st.expander("All rooms and downloads"):
            st.dataframe(ctx["stats"][columns].round(1), hide_index=True, width="stretch")
            csv_download(ctx["stats"][columns], "Download room comparison", "neat-room-comparison.csv", "room_comparison_csv")
            raw = ctx["data"][(ctx["data"]["Room key"] == room) & ctx["data"].Timestamp.between(ctx["start"], ctx["end"])]
            csv_download(raw, "Download source observations for this room", "neat-room-observations.csv", "room_source_csv")
    u.footer()


def environment():
    u.shell("Environment", "Comfort with a clearer purpose.", "Spot recurring conditions, protect the room experience and investigate avoidable operation.")
    v.styles()
    ctx = u.context()
    room = choose_room(ctx)
    selected_issues=ctx["issues"][ctx["issues"]["Room key"].eq(room) & ctx["issues"].Kind.isin(["warm","light"])]
    title = ("This room has empty-time conditions worth investigating." if not selected_issues.empty
             else "No repeated empty-room signals meet your review settings.")
    c.answer("The facilities decision",title,"Check actual HVAC and lighting operation before changing settings. Temperature and light readings alone do not establish energy use or savings.","sunset")
    with st.container(key="panel_environment"):
        u.section("Room conditions", "environment")
        signal = v.condition_tiles(ctx, room)
        seg = ctx["samples"][ctx["samples"]["Room key"] == room]
        valid = seg[signal].notna() & seg["Device Status"].isin(["Online", "Unreported"])
        hours = seg.loc[valid, "Hours"].sum()
        scheduled = a.window_hours(ctx["start"], ctx["end"], ctx["office"])
        room_trend(ctx, room, signal, "environment_history")
        with st.expander("Sensor coverage and interpretation"):
            st.write(f"{signal} observation coverage: {u.fmt(100 * hours / scheduled if scheduled else np.nan, '%')} \xb7 {hours:.1f} observed hours")
            st.caption("Review colours indicate the selected investigation levels, not a confirmed fault or health rating. Latest selected records can be historical.")
            if signal == "VOC": st.write("VOC is shown in source units. Confirm whether the collector supplies VOC Index or concentration before applying a threshold; this is not measured CO\u2082.")
    with st.container(key="panel_environment_findings"):
        u.section("Where facilities can focus next", "focus", "environment")
        st.caption("Across the selected scope \xb7 warmth and brightness alone do not establish energy use")
        finding_rows(ctx["issues"][ctx["issues"].Kind.isin(["warm", "light"])], "environment", 10, environment_evidence=True)
    with st.expander("Connect conditions to the experience demo"):
        c.experience_bridge(ctx,room)
    environment_actions(ctx, room)
    u.footer()


def insights():
    u.shell("Insights", "Turn opportunity into a plan.", "Choose a focused improvement, give it an owner and agree how you will measure success.")
    v.styles()
    ctx = u.context()
    counts=c.opportunity_counts(ctx)
    c.answer("Your improvement pipeline",f"{ctx['issues']['Room key'].nunique()} rooms have evidence to explore.",
             "Start with a small pilot. Compare the room evidence, model the cost, then verify the effect on use and real user experience.","forest")
    for column,(label,value,detail,tone) in zip(st.columns(3),[
        ("Room mix",counts["fit"],"Rooms with consistently small observed groups","rain"),
        ("Temperature",counts["warm"],"Rooms warm during observed empty periods","sunset"),
        ("Lighting",counts["light"],"Rooms bright during observed empty periods","sunrise")]):
        with column:c.stat(label,str(value),detail,tone,"Pulse observations")
    st.caption("A room can appear in more than one theme. These are investigation candidates, not confirmed faults or savings.")
    with st.container(key="panel_insights"):
        u.section("Evidence to take into the next conversation", "focus", "insights")
        labels = {"All findings": None, "Room fit": "fit", "Warm while empty": "warm", "Bright while empty": "light"}
        choice = st.selectbox("Finding type", list(labels))
        issues = ctx["issues"]
        if labels[choice]: issues = issues[issues.Kind == labels[choice]]
        st.caption(f"{len(issues)} findings \xb7 ordered by qualifying observed hours; this is not a financial ranking")
        finding_rows(issues, "insights")
        csv_download(issues.drop(columns=["Rank", "Kind"]), "Download evidence and next steps", "neat-findings.csv", "insights_csv")
    with st.expander("What would strengthen the business case?"):
        st.write("**Bookings** establish whether an empty room was actually reserved. **Building controls** establish whether HVAC or lighting was operating. **Energy meters and an agreed baseline** support measured savings. Link those sources to the same room identifier and timestamps before reporting no-shows or financial outcomes.")
    left,right=st.columns(2)
    with left:st.page_link("pages/Scenarios.py",label="Test a layout change",icon=":material/compare_arrows:")
    with right:st.page_link("pages/Value.py",label="Assess cost and return",icon=":material/finance_mode:")
    u.footer()


def operations():
    u.shell("Operations", "Keep the experience ready.", "See which rooms need an operational check and give the right team useful evidence.")
    v.styles()
    ctx = u.context()
    inv = ctx["inventory"]
    online=int(inv["Device Status"].eq("Online").sum())
    offline=int(inv["Device Status"].eq("Offline").sum())
    other=len(inv)-online-offline
    latest=inv.Timestamp.max()
    stale=(latest-inv.Timestamp).dt.total_seconds().gt(3600)
    c.answer("The readiness decision",f"{online} of {len(inv)} rooms were last reported online.",
             "Review offline, unknown and older records before a visit or important meeting. This is the selected period's last snapshot, not a live room-readiness guarantee.","rain")
    for column,(label,value,detail,tone) in zip(st.columns(4),[
        ("Online",online,"Latest selected room status","forest"),("Offline",offline,"Check device and network status","sunset"),
        ("Unknown / unreported",other,"Do not assume these rooms are online","sunrise"),
        ("Older room records",int(stale.sum()),"Over 1 hour behind the latest room record","rain")]):
        with column:c.stat(label,str(value),detail,tone)
    with st.container(key="panel_fleet"):
        u.section("Latest recorded room state", "fleet")
        st.caption("One latest record per named room \xb7 timestamps reflect the selected date range")
        columns = ["Room Name", "Location", "Device Status", "Platform", "Software Version", "Timestamp"]
        display=inv.assign(Review=~inv["Device Status"].eq("Online") | stale).sort_values(["Review","Timestamp","Room Name"],ascending=[False,True,True])
        st.html('<div class="room-status-grid">'+''.join(
            f'<article class="room-status-card {"review" if row.Review else ""}"><div class="state">{escape(row["Device Status"].upper())}{" · OLDER RECORD" if latest-row.Timestamp>pd.Timedelta(hours=1) else ""}</div>'
            f'<strong>{escape(row["Room Name"])}</strong><span>{escape(row.Location)} · {escape(row.Platform)}</span><br><small>{row.Timestamp:%d %b %Y, %H:%M} · source clock</small></article>'
            for _,row in display.head(12).iterrows())+'</div>')
        if len(display)>12:st.caption("Showing the first 12 rooms, with checks first. All records are available below.")
        with st.expander("All room records and platform mix"):
            st.dataframe(inv[columns].sort_values(["Device Status", "Room Name"]), hide_index=True, width="stretch")
            platforms=inv.Platform.value_counts()
            fig=go.Figure(go.Bar(x=platforms.values,y=platforms.index,orientation="h",marker_color="#93ABB3",text=platforms.values,textposition="auto",
                hovertemplate="%{y}<br>%{x} named rooms<extra></extra>"))
            u.plot_style(fig,max(180,45*len(platforms)))
            fig.update_xaxes(title="Named rooms",dtick=1)
            chart(fig,"fleet_platforms")
            csv_download(inv[columns], "Download room state", "neat-room-state.csv", "fleet_csv")
    with st.container(key="panel_workflow"):
        u.section("Preview a facilities handoff", "workflow")
        st.caption("Draft export only \xb7 no ticket, device command or building control is sent")
        issues = ctx["issues"]
        if issues.empty: st.write("A qualifying finding will make an evidence-backed handoff available here.")
        else:
            idx = st.selectbox("Finding to include", list(issues.index), format_func=lambda i: f"{issues.loc[i, 'Room key']} \xb7 {issues.loc[i, 'Finding']}")
            r = issues.loc[idx]
            c.next_step(f"{r.Owner}: {r['Next step']}")
            st.write(f"**{r['Room key']}** · {r.Evidence}")
            payload = {"status": "draft_not_sent", "demonstration_data": bool(st.session_state.get("demo_mode")),
                       "room": r["Room key"], "finding": r.Finding, "evidence": r.Evidence,
                       "period_start": ctx["start"].isoformat(), "period_end": ctx["end"].isoformat(),
                       "clock": "recorded_source_time", "operating_hours": "weekdays_08_19" if ctx["office"] else "all_hours",
                       "evidence_hours": float(r["Evidence hours"]), "investigation_thresholds": ctx["thresholds"],
                       "suggested_owner": r.Owner, "proposed_next_step": r["Next step"], "confirmed_energy_savings": None}
            with st.expander("Technical handoff details"):
                st.json(payload, expanded=False)
            st.download_button("Download draft handoff", json.dumps(payload, indent=2), "neat-handoff-draft.json", "application/json")
    u.footer()


def ask():
    u.shell("Ask the data", "A useful answer. A clear next step.", "Start with the customer question and follow the evidence into the right decision.")
    v.styles()
    ctx = u.context()
    with st.container(key="panel_ask"):
        u.section("Explore a question", "ask")
        question = st.selectbox("What would you like to understand?", ["Where should we focus first?", "Which rooms may be oversized?", "Where should facilities investigate?", "Which rooms were last reported offline?", "How much of the period did we observe?", "Can we show a return on investment?", "How would user feedback change the conversation?"])
        if question == "Where should we focus first?":
            actions=decision_actions(ctx)
            c.answer("Start here",actions[0]["title"],actions[0]["action"],"forest")
            finding_rows(ctx["issues"].drop_duplicates("Room key"), "ask_priority", 3)
            st.page_link("pages/Insights.py",label="Open the improvement opportunities",icon=":material/arrow_forward:")
        elif question == "Which rooms may be oversized?":
            found=ctx["issues"][ctx["issues"].Kind.eq("fit")]
            c.answer("Room fit",f"{found['Room key'].nunique()} rooms meet the room-fit review rules.","Check peaks, room purpose and bookings before changing capacity.","rain")
            finding_rows(found, "ask_fit")
            st.page_link("pages/Scenarios.py",label="Test an alternative layout",icon=":material/compare_arrows:")
        elif question == "Where should facilities investigate?": finding_rows(ctx["issues"][ctx["issues"].Kind.isin(["warm", "light"])], "ask_facilities")
        elif question == "Which rooms were last reported offline?":
            offline = ctx["inventory"][ctx["inventory"]["Device Status"].eq("Offline")]
            if offline.empty: st.write("No rooms were reported offline in their latest selected record.")
            else: st.dataframe(offline[["Room Name", "Location", "Timestamp", "Device Status"]], hide_index=True, width="stretch")
            st.caption("Unknown states are not counted as online. Review Operations for the full snapshot.")
        elif question == "Can we show a return on investment?":
            c.answer("The honest answer","You can model a return. It is not yet a measured outcome.","Pulse supplies room-use evidence. A financial case also needs project cost, cash savings and ongoing cost assumptions, followed by verification.","sunrise")
            st.page_link("pages/Value.py",label="Build the investment case",icon=":material/finance_mode:")
        elif question == "How would user feedback change the conversation?":
            c.experience_bridge(ctx)
        else:
            s = ctx["summary"]
            st.write(f"**{u.fmt(s['coverage'], '%')}** occupancy observation coverage: {s['valid_hours']:,.1f} valid room-hours out of {s['expected_hours']:,.1f} scheduled room-hours.")
            st.write("Missing samples, missing occupancy and offline or unknown device states reduce coverage. They do not become empty-room time.")
            st.dataframe(ctx["stats"][["Room Name", "Location", "Observed hours", "Coverage %"]].round(1), hide_index=True, width="stretch")
    st.caption("Guided answers use the dashboard's calculations. This is not a connected AI chat service.")
    u.footer()
