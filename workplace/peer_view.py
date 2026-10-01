from html import escape
import pandas as pd
import streamlit as st
from workplace import ui as u
from workplace.peers import compare_peer


@st.cache_data(max_entries=24, show_spinner=False)
def cached_peer(_data, fetched, room, start, end, office):
    return compare_peer(_data, room, start, end, office)


def automatic_peer(ctx, room):
    with st.container(key="panel_automatic_peer"):
        st.subheader("A similar room. Automatically.")
        data = ctx["all_data"]
        if not ctx["demo"]:
            data = data[data.Location.isin(["London EC", "Oslo EC"])]
        result = cached_peer(data, ctx["fetched"], room, ctx["start"], ctx["end"], ctx["office"])
        if result is None:
            st.info("No similarly sized room has records in this date range. A match needs capacity within 25% or two seats of this room.")
            return
        current, peer = result
        difference = abs(peer.Capacity - current.Capacity)
        match = "Same capacity" if difference == 0 else f"{difference:g}-seat difference"
        st.caption(f"{match} · {peer['Room Name']} in {peer.Location} selected automatically. Same dates and operating hours for both rooms.")
        for column, row, tint, label in zip(st.columns(2), [current, peer], ["#EDF1FA", "#ECE7F5"], ["SELECTED ROOM", "AUTOMATIC MATCH"]):
            util = row["Utilisation %"]
            width = 0 if pd.isna(util) else max(0, min(100, util))
            with column:
                st.html(f'''<article style="padding:20px;border-radius:14px;background:{tint}">
                  <div class="small-muted">{label} · {u.fmt(row.Capacity)} SEATS</div>
                  <h3 style="margin:6px 0;padding:0;font-size:24px">{escape(row['Room Name'])}</h3>
                  <div class="small-muted">{escape(row.Location)}</div>
                  <div style="font-size:38px;font-weight:700;margin-top:12px">{u.fmt(util, '%')}</div>
                  <div class="small-muted">Time in use</div>
                  <div style="height:9px;background:#D5DCE8;border-radius:5px;margin:12px 0;overflow:hidden"><div style="width:{width}%;height:100%;background:#6A87D0"></div></div>
                  <div style="display:flex;justify-content:space-between;font-size:13px;gap:15px">
                    <span><strong>{u.fmt(row['Typical attendance'], digits=1)}</strong> typical people</span>
                    <span><strong>{u.fmt(row['Coverage %'], '%')}</strong> coverage</span>
                  </div></article>''')
        if any(pd.isna(r["Coverage %"]) or r["Coverage %"] < 70 for r in result):
            st.warning("One of these rooms has limited coverage. The observed periods may not represent the full date range.")
        with st.expander("How the automatic match works"):
            st.write("Search all meeting rooms in London EC and Oslo EC, including rooms outside your location and room filters. Match the closest capacity first, then the same location; break ties with coverage and room name. Only rooms with records in the selected dates qualify.")
            st.caption("Capacity is the matching criterion. Room purpose, equipment, bookings and local working patterns may differ. This comparison describes observations, not a controlled performance ranking.")
