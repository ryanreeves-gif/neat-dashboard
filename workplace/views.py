        u.section("Findings for this room", "focus", "room")
        found = ctx["issues"][ctx["issues"]["Room key"] == room]
        if found.empty: st.write("No findings meet the current evidence thresholds.")
        for _, f in found.iterrows():
            st.write(f"**{f.Finding}** \u2014 {f.Evidence}")
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
        st.caption(f"{signal} observation coverage: {u.fmt(100 * hours / scheduled if scheduled else np.nan, '%')} \xb7 {hours:.1f} observed hours")
        room_trend(ctx, room, signal, "environment_history")
        if signal == "VOC": st.caption("VOC is shown in source units. Confirm whether the collector supplies VOC Index or concentration before applying a threshold; this is not measured CO\u2082.")
    environment_actions(ctx, room)
    with st.container(key="panel_environment_findings"):
        u.section("Conditions to investigate", "focus", "environment")
        st.caption("Across the selected scope \xb7 warmth and brightness alone do not establish energy use")
        finding_rows(ctx["issues"][ctx["issues"].Kind.isin(["warm", "light"])], "environment", 10, environment_evidence=True)
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
        st.caption(f"{len(issues)} findings \xb7 ordered by qualifying observed hours; this is not a financial ranking")
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
        st.caption("One latest record per named room \xb7 timestamps reflect the selected date range")
        columns = ["Room Name", "Location", "Device Status", "Platform", "Software Version", "Timestamp"]
        st.dataframe(inv[columns].sort_values(["Device Status", "Room Name"]), hide_index=True, width="stretch")
        st.dataframe(inv.Platform.value_counts().rename_axis("Platform").reset_index(name="Rooms"), hide_index=True, width="stretch")
        csv_download(inv[columns], "Download room state", "neat-room-state.csv", "fleet_csv")
    with st.container(key="panel_workflow"):
        u.section("Preview a facilities handoff", "workflow")
        st.caption("Draft export only \xb7 no ticket, device command or building control is sent")
        issues = ctx["issues"]
        if issues.empty: st.write("A qualifying finding will make an evidence-backed handoff available here.")
        else:
            idx = st.selectbox("Finding to include", list(issues.index), format_func=lambda i: f"{issues.loc[i, 'Room key']} \xb7 {issues.loc[i, 'Finding']}")
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
