"""Graphic room availability and an explicitly simulated Teams sign-in alert."""
from html import escape

import streamlit as st

from workplace import ui as u
from workplace.health import current_demo, make_demo


def technology(ctx, case):
    from workplace.briefing import html, heading, metrics, preferred_room
    preferred_room(ctx)
    inv = ctx["inventory"].sort_values("Room key")
    eligible = inv[inv.Platform.eq("Microsoft Teams")]
    selected = None
    demo = current_demo(ctx, st.session_state)
    if len(eligible):
        options = eligible["Room key"].tolist()
        if st.session_state.get("health_demo_room") not in options:
            st.session_state["health_demo_room"] = next((r for r in options if r.endswith(" / Barra")), options[0])
        # A compact room selector is the only setup needed on the main screen.
        selected = st.selectbox("Teams room for the sign-in example", options,
                                **u.field_state("health_demo_room", options[0]))
        if demo is None or demo["room"] != selected:
            demo = make_demo(ctx, selected, 0)
            st.session_state["health_demo"] = demo
    else:
        st.session_state.pop("health_demo", None)
        demo = None
    with ctx["tools"].expander("Sign-in demonstration and live integration"):
        st.write("These are invented events, not the received Neat or Microsoft webhook payload. Their illustrative timestamps fall within the selected date range. The recorded device status is never changed by the example.")
        st.write("For a live connection: verify a redacted real event, authenticate the receiver, map stable device/room IDs, persist and deduplicate events, handle delayed deliveries and verify explicit recovery. Reconcile with an initial status snapshot and monitor event freshness; silence must not mean healthy.")
        st.caption("No endpoint, credentials, ticketing or remote sign-in action is connected. A signed-in account does not establish camera, microphone, calendar or call health.")
        if demo:
            st.json(demo["events"], expanded=False)
            if st.button("Reset sign-in example", key="health_reset"):
                st.session_state["health_demo"] = make_demo(ctx, selected, 0)
                st.rerun()
    html('<div class="brief-demo-banner"><b>Two sources:</b> device availability is recorded telemetry; Microsoft sign-in is a labelled simulation. No live webhook is connected.</div>')
    online = int(inv["Device Status"].eq("Online").sum())
    metrics([
        ("Last reported online", f"{online} / {len(inv)}", "Latest record in the selected period", "Sample telemetry" if ctx["demo"] else "Recorded device status", "forest", False),
        ("Availability to check", str(len(inv) - online), "Offline, unknown or unreported", "Recorded status · not a live check", "rain", False),
        ("Microsoft Teams rooms", str(len(eligible)), "Rooms in the selected scope", "Recorded platform", "purple", False),
        ("Sign-in alerts · demo", "1" if demo and demo["stage"] == 1 else "0", "One-room example only", "Simulated · live estate total unknown", "sunrise", False),
    ])
    left, right = st.columns([1.45, 1], gap="medium")
    with left, st.container(key="brief_panel_health_grid"):
        heading("Room technology at a glance", "Recorded availability and sign-in are separate checks")
        cards = []
        ordered = inv.assign(_selected=inv["Room key"].eq(selected)).sort_values(["_selected", "Room key"], ascending=[False, True])
        for _, row in ordered.head(12).iterrows():
            is_demo = demo and row["Room key"] == demo["room"]
            signin = (demo["status"] + " · DEMO") if is_demo else "Not connected" if row.Platform == "Microsoft Teams" else "Not applicable"
            tone = "alert" if is_demo and demo["stage"] == 1 else "example" if is_demo else ""
            status_class = "online" if row["Device Status"] == "Online" else "unknown"
            cards.append(f'<article class="health-room {tone}"><h3>{escape(row["Room Name"])}</h3>'
                         f'<span>{escape(row.Platform)}</span><div><i class="{status_class}"></i>Device: {escape(row["Device Status"])}</div>'
                         f'<div class="health-signin">Teams sign-in: <b>{escape(signin)}</b></div>'
                         f'<small>Recorded {row.Timestamp:%d %b, %H:%M}</small></article>')
        html('<div class="health-room-grid">' + ''.join(cards) + '</div>')
        if len(inv) > 12:
            st.caption(f"Showing 12 of {len(inv)} rooms. Use the room filter to focus the view.")
        st.caption("Historical snapshots in the source clock. Online status alone does not confirm that a meeting will work.")
    with right, st.container(key="brief_panel_signin_demo"):
        heading("From alert to action", "Microsoft Teams sign-in · simulated example")
        if not demo:
            st.info("No Microsoft Teams room is in the current scope. Choose a location or room filter that includes one to try this example.")
            return
        row = inv.set_index("Room key").loc[demo["room"]]
        stage = demo["stage"]
        title = ["Signed in", "Sign-in needs attention", "Sign-in restored"][stage]
        detail = ["Example baseline · no sign-in issue in this scenario.",
                  "Simulated sign-out alert · this Teams account needs IT attention.",
                  "Simulated recovery event · verify a test meeting before closing the issue."][stage]
        colour = "alert" if stage == 1 else "good"
        html(f'<div class="health-demo-state {colour}"><span class="health-demo-tag">SIMULATED · {escape(row["Room Name"])}</span>'
             f'<div class="health-monitor"><span>{"!" if stage == 1 else "✓"}</span></div><h2>{title}</h2><p>{detail}</p></div>')
        button = "Simulate sign-in recovery" if stage == 1 else "Simulate sign-out alert" if stage == 0 else "Replay sign-out example"
        if st.button(button, key="health_advance", type="primary", width="stretch"):
            st.session_state["health_demo"] = make_demo(ctx, selected, 2 if stage == 1 else 1)
            st.rerun()
        html('<div class="health-sequence">' + ''.join(
            f'<span class="{"reached" if i <= stage else ""}"><b>{i+1}</b>{label}</span>'
            for i, label in enumerate(["Baseline", "Sign-out", "Recovery"])) + '</div>')
        html('<div class="brief-insight"><b>Owner: IT / room support</b>Check the room-account sign-in details, restore access and verify a test meeting. No ticket or notification is sent by this example.</div>')
    html('<div class="brief-closing"><b>Catch the issue before the next meeting.</b><span>Measure time to detect, time to restore and repeated incidents once real events are connected.</span></div>')
