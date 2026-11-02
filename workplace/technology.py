"""Room-level technology snapshot; never infer device health or updates."""
from html import escape

import pandas as pd
import streamlit as st

from workplace.conclusions import equipment_details


def technology_snapshot(inventory):
    """One last reported observation per room, respecting the existing scope."""
    records = []
    for _, room in inventory.iterrows():
        equipment = equipment_details(room.get("Neat Equipment"))
        models = equipment["video"] + equipment["other"]
        if equipment["unmapped"]:
            models += ["Other model codes: " + ", ".join(equipment["unmapped"])]
        status = str(room.get("Device Status", "Unreported")).strip().title()
        status = status if status in {"Online", "Offline"} else "Not reported"
        version = room.get("Software Version")
        platform = room.get("Platform")
        def known(value):
            return str(value).strip() if pd.notna(value) and str(value).strip().lower() not in {"", "unknown", "none", "nan", "unreported"} else "Not reported"
        timestamp = pd.to_datetime(room.get("Timestamp"), errors="coerce")
        records.append({"Room": str(room.get("Room key", "Unknown")),
                        "Last status": status,
                        "Video setup": " + ".join(models) if models else "Not reported",
                        "Platform": known(platform), "Software version": known(version),
                        "Last observation": timestamp.strftime("%d %b %Y, %H:%M") if pd.notna(timestamp) else "Not reported"})
    return pd.DataFrame(records, columns=["Room", "Last status", "Video setup", "Platform", "Software version", "Last observation"])


def render(ctx):
    snapshot = technology_snapshot(ctx["inventory"])
    total = len(snapshot)
    online = int(snapshot["Last status"].eq("Online").sum())
    offline = int(snapshot["Last status"].eq("Offline").sum())
    unknown = total - online - offline
    versioned = int(snapshot["Software version"].ne("Not reported").sum())
    status_caption = f"{offline} offline · {unknown} not reported"
    room_label = "room" if total == 1 else "rooms"
    if offline:
        recommendation = "Investigate the offline room sources, then confirm device and meeting-service readiness."
    elif unknown:
        recommendation = "Check the rooms with missing status before assessing estate readiness."
    else:
        recommendation = "Check live device health and update availability before planning maintenance."
    st.html(
        '<section class="technology-overview" aria-label="Technology estate snapshot">'
        '<div class="technology-head"><div><span>TECHNOLOGY · ESTATE SNAPSHOT</span>'
        '<h2>Is the technology ready?</h2>'
        '<p>Latest reported room-source status within the selected dates, not a live device health check.</p></div>'
        '<div class="technology-action"><b>IT next step</b>' + escape(recommendation) + '</div></div>'
        '<div class="technology-metrics">'
        f'<div><span>Last reported online</span><strong>{online} <small>/ {total} {room_label}</small></strong><p>{escape(status_caption)}</p></div>'
        f'<div><span>Software version reported</span><strong>{versioned} <small>/ {total} {room_label}</small></strong><p>Source version, not every device</p></div>'
        '<div><span>Updates available</span><strong class="technology-unknown">Not connected</strong><p>Requires a live update feed</p></div>'
        '</div></section>'
    )
    with st.expander("View room technology and software versions"):
        st.caption("Each row is the latest room observation in the selected date range. Status and software version describe its reporting source; equipment may contain multiple products. They do not confirm the health, sign-in or software of every device. Product models are a snapshot; unknown codes are retained. Update availability and sign-in status are not supplied.")
        st.dataframe(snapshot, hide_index=True, width="stretch", column_config={
            "Room": st.column_config.TextColumn("Room", width="medium"),
            "Video setup": st.column_config.TextColumn("Reported products", width="large"),
            "Software version": st.column_config.TextColumn("Source software", width="medium"),
        })
