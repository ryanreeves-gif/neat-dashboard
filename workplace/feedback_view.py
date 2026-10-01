from __future__ import annotations

import base64
from hashlib import sha256
from html import escape
from uuid import uuid4
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from workplace import analytics as a, ui as u, customer as c
from workplace.data import load
from workplace.feedback import AUDIENCES, ISSUES, demo_record, feedback_summary, filter_feedback, sample_feedback
from workplace.views import choose_room, csv_download

COLOURS = ["#D69B8C", "#D5B68F", "#DBC684", "#93ABB3", "#638C7D"]
FACES = {1: "1 😞", 2: "2 🙁", 3: "3 😐", 4: "4 🙂", 5: "5 😄"}


def styles():
    st.html((u.ROOT / "assets/feedback.css").read_text())


@st.cache_data(max_entries=4, show_spinner=False)
def generated_feedback(_data, fetched):
    return sample_feedback(_data)


def start_again():
    st.session_state.pop("frame_complete", None)
    st.session_state.pop("frame_help", None)
    st.session_state["frame_round"] = st.session_state.get("frame_round", 0) + 1


def portrait_survey(room):
    token = sha256(room["Room key"].encode()).hexdigest()[:12] + f"_{st.session_state.get('frame_round', 0)}"
    with st.container(key="frame_screen"):
        logo = base64.b64encode((u.ROOT / "assets/neat-logo.svg").read_bytes()).decode()
        st.html(f'<div class="frame-brand"><img src="data:image/svg+xml;base64,{logo}" alt="Neat" width="85" height="44"></div><div class="frame-room">{escape(room["Room Name"])} · {escape(room["Location"])}</div>')
        if st.session_state.get("frame_complete") == room["Room key"]:
            st.html('<div class="frame-thanks"><div class="tick">✓</div><h2>Thanks for sharing.</h2><p>Your experience helps shape better spaces.</p></div>')
            st.caption("Demo response added to this browser session. It is separate from the historical sample results.")
            st.button("Next person", key="frame_next", on_click=start_again, type="primary", width="stretch")
        else:
            st.html('<h2 class="frame-title">How was your<br>experience?</h2><p class="frame-intro">A few taps. A better space for everyone.</p>')
            with st.form("frame_form_" + token, border=False):
                audience = st.segmented_control("I am a…", AUDIENCES, key="frame_audience_" + token,
                                               required=True, width="stretch")
                experience = st.segmented_control("The space", list(FACES), format_func=FACES.get,
                    key="frame_experience_" + token, required=True, width="stretch")
                st.html('<div class="frame-scale"><span>1 · Poor</span><span>5 · Excellent</span></div>')
                equipment = st.segmented_control("The equipment", list(FACES), format_func=FACES.get,
                    key="frame_equipment_" + token, required=True, width="stretch")
                st.html('<div class="frame-scale"><span>1 · Poor</span><span>5 · Excellent</span></div>')
                issue = st.selectbox("Anything we could improve? (optional)", ["Nothing to flag", *ISSUES], key="frame_issue_" + token)
                comment = st.text_input("A few words? (optional)", max_chars=300, placeholder="What made the difference?", key="frame_comment_" + token)
                submitted = st.form_submit_button("Share feedback", type="primary", width="stretch")
            if submitted:
                if audience is None or experience is None or equipment is None:
                    st.warning("Please choose employee or guest and rate both the space and equipment.")
                else:
                    record = demo_record(room, audience, experience, equipment,
                        "" if issue == "Nothing to flag" else issue, comment.strip(),
                        timestamp=pd.Timestamp.now(tz="UTC").tz_localize(None), response_id="TRY-" + uuid4().hex,
                        source="Interactive demonstration", clock="UTC")
                    st.session_state.setdefault("feedback_tryouts", []).append(record)
                    st.session_state["frame_complete"] = room["Room key"]
                    st.rerun()
        if st.button("Get IT help", icon=":material/support_agent:", key="frame_it", width="stretch"):
            st.session_state["frame_help"] = room["Room key"]
        if st.session_state.get("frame_help") == room["Room key"]:
            st.info("Demo: this would connect you to the showroom team or create a room-specific support request. No request has been sent.")
        st.html('<div class="feedback-small">Interactive demonstration · Session only<br>Please avoid names or personal details.</div>')


def metric_card(label, value, detail, colour):
    st.html(f'<div class="feedback-metric {colour}"><div class="label">{escape(label)}</div><strong>{escape(value)}</strong><span>{escape(detail)}</span></div>')


def results(records, audience):
    summary = feedback_summary(records)
    for col, (label, value, detail, colour) in zip(st.columns(4), [
        ("Sample responses", f"{summary['responses']:,}", "Invented responses in this scope", ""),
        ("Enjoyed the space", u.fmt(summary["positive"], "%", 1) if len(records) else "—", "Rated the space 4 or 5 out of 5", "green"),
        ("Space experience", u.fmt(summary["experience"], " / 5", 2) if len(records) else "—", "Average sample rating", "blue"),
        ("Equipment experience", u.fmt(summary["equipment"], " / 5", 2) if len(records) else "—", "Average sample rating", "gold")]):
        with col:
            metric_card(label, value, detail, colour)
    if records.empty:
        st.info("No sample responses in this selection. Try a wider date range or another room.")
        return
    left, right = st.columns([1, 1.2], gap="medium")
    with left, st.container(key="panel_feedback_ratings"):
        st.subheader("How the spaces feel")
        counts = records.experience.value_counts().reindex(range(1, 6), fill_value=0)
        fig = go.Figure(go.Bar(x=["1 · Poor", "2", "3", "4", "5 · Excellent"], y=counts.values,
            marker_color=COLOURS, text=counts.values, textposition="outside", cliponaxis=False,
            hovertemplate="%{x}<br>%{y} sample responses<extra></extra>"))
        u.plot_style(fig, 290)
        fig.update_yaxes(title="Sample responses", rangemode="tozero", range=[0, max(counts.max()*1.2, 1)])
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="feedback_distribution")
    with right, st.container(key="panel_feedback_trend"):
        st.subheader("Experience over time")
        d = records.assign(day=records.timestamp.dt.normalize())
        frequency = "W-MON" if (d.day.max() - d.day.min()).days > 31 else "D"
        fig = go.Figure()
        for group, colour in zip(AUDIENCES, ["#638C7D", "#5F259F"]):
            g = d[d.audience.eq(group)].groupby(pd.Grouper(key="day", freq=frequency)).agg(score=("experience", "mean"), n=("experience", "size"))
            if not g.empty:
                fig.add_trace(go.Scatter(x=g.index, y=g.score, customdata=g.n, name=group, mode="lines+markers",
                    line=dict(color=colour, width=3), connectgaps=False,
                    hovertemplate="%{x|%d %b}<br>%{y:.2f} / 5<br>%{customdata} sample responses<extra>%{fullData.name}</extra>"))
        u.plot_style(fig, 290)
        fig.update_yaxes(title="Space rating / 5", range=[1, 5.2], dtick=1)
        fig.update_layout(legend=dict(orientation="h", y=1.2, x=0), margin=dict(t=40))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="feedback_trend")
        st.caption("Weekly averages, labelled by week ending Monday." if frequency != "D" else "Daily averages. Gaps mean no sample responses.")
    with st.container(key="panel_feedback_audiences"):
        st.subheader("Employees and showroom guests")
        groups = [group for group in AUDIENCES if group in set(records.audience)]
        for column, group in zip(st.columns(len(groups)), groups):
            g = records[records.audience.eq(group)]
            s = feedback_summary(g)
            with column:
                st.markdown(f"**{group}**")
                st.progress(float(s["positive"] / 100), text=f"{s['positive']:.1f}% positive · {len(g):,} sample responses")
                st.caption(f"Space {s['experience']:.2f} / 5 · Equipment {s['equipment']:.2f} / 5")
        st.caption("Guests are deliberately very positive in this demonstration. These figures are not measured satisfaction or a representative survey.")
    st.subheader("Voices from the showroom")
    quotes = records[records.experience.ge(4) & records.equipment.ge(4)].drop_duplicates(["audience", "comment"])
    # Prefer one voice from each audience before filling the remaining cards.
    firsts = quotes.drop_duplicates("audience")
    quotes = pd.concat([firsts, quotes.drop(firsts.index)]).head(3)
    for col, (_, row) in zip(st.columns(max(1, len(quotes))), quotes.iterrows()):
        with col:
            st.html(f'<div class="feedback-quote"><p>“{escape(row.comment)}”</p><small>SAMPLE COMMENT · {escape(row.audience)}<br>{escape(row.room_name)} · {row.timestamp:%d %b %Y}</small></div>')
    with st.expander("Room results and things to improve"):
        table = records.groupby(["room_key", "audience"]).agg(Responses=("experience", "size"),
            Space=("experience", "mean"), Equipment=("equipment", "mean"), Positive=("experience", lambda x: 100*x.ge(4).mean())).reset_index()
        table.columns = ["Room", "Audience", "Sample responses", "Space / 5", "Equipment / 5", "Positive %"]
        st.dataframe(table.round(2), hide_index=True, width="stretch")
        flags = records.loc[records.issue.ne(""), "issue"].value_counts().rename_axis("Optional issue").reset_index(name="Sample mentions")
        st.dataframe(flags, hide_index=True, width="stretch")
        st.caption("Optional issue mentions are separate from the satisfaction score. No support tickets are created from these sample records.")


def session_results():
    rows = st.session_state.get("feedback_tryouts", [])
    st.subheader("Your demo submissions")
    if not rows:
        st.caption("Try the portrait screen to add a response here.")
        return
    st.success(f"{len(rows)} demo response{'s' if len(rows) != 1 else ''} in this browser session.")
    st.caption("Recorded at the time you submitted, in UTC. Kept separate from historical samples and cleared when this session ends.")
    df = pd.DataFrame(rows)
    st.dataframe(df[["timestamp", "room_name", "audience", "experience", "equipment", "issue"]], hide_index=True, width="stretch")
    csv_download(df, "Download my demo submissions", "neat-feedback-tryouts-DEMO.csv", "feedback_tryout_export")


def use_and_experience(ctx, records):
    if records.empty:
        return
    ratings=records.groupby("room_key").agg(Rating=("experience","mean"),Responses=("experience","size")).reset_index()
    combined=ctx["stats"].merge(ratings,left_on="Room key",right_on="room_key").dropna(subset=["Utilisation %"])
    if combined.empty:
        return
    with st.container(key="panel_use_experience"):
        st.html('<span class="source-tag sample">Pulse use + synthetic sentiment · demonstration overlay</span>')
        st.subheader("Room use is only half the story.")
        st.caption("A future live view can show whether busy rooms are also enjoyable. Here the ratings are invented; they cannot establish a real relationship with use.")
        fig=go.Figure(go.Scatter(x=combined["Utilisation %"],y=combined.Rating,mode="markers+text",text=combined["Room Name"],textposition="top center",
            marker=dict(size=(combined.Responses/combined.Responses.max()*22+14),color="#5F259F",opacity=.65,line=dict(color="white",width=1.5)),
            customdata=combined[["Room key","Responses","Coverage %"]],
            hovertemplate="%{customdata[0]}<br>Observed time in use: %{x:.1f}%<br>Sample space rating: %{y:.2f} / 5<br>%{customdata[1]} sample responses<br>Occupancy coverage: %{customdata[2]:.0f}%<extra></extra>"))
        u.plot_style(fig,350)
        fig.update_xaxes(title="Time in use · Pulse observations (%)",range=[-4,104],ticksuffix="%")
        fig.update_yaxes(title="Space rating · sample feedback / 5",range=[.8,5.35],dtick=1)
        st.plotly_chart(fig,width="stretch",config={"displayModeBar":False},key="feedback_use_relationship")
        st.caption("Each bubble is a room. Bubble size reflects sample response count; hover for coverage. All room and audience filters apply.")


def feedback_page():
    u.shell("Feedback", "Great spaces start with people.", "Understand what employees and guests value, where friction appears and how to measure a better experience.")
    styles()
    ctx = u.context(show_evidence=False)
    records = generated_feedback(ctx["all_data"], ctx["fetched"])
    source = ctx["data"][ctx["data"]["Room key"].isin(ctx["inventory"]["Room key"])]
    st.html(f'''<div class="feedback-banner"><strong>Demonstration data · Invented ratings and comments</strong>
      <span>Sample feedback follows the room feed's history: {source.Timestamp.min():%d %b %Y}–{source.Timestamp.max():%d %b %Y}.
      Employees are positive; guests are deliberately very positive. No real survey responses are connected.</span></div>''')
    result_tab, frame_tab = st.tabs(["Experience results", "Try the Neat Frame demo"])
    with result_tab:
        audience = st.segmented_control("Show feedback from", ["Everyone", *AUDIENCES], required=True, width="stretch",
                                       **u.field_state("feedback_audience", "Everyone"))
        filtered = filter_feedback(records, ctx["inventory"]["Room key"], ctx["start"], ctx["end"], ctx["office"], audience)
        results(filtered, audience)
        use_and_experience(ctx, filtered)
        c.next_step("In a live pilot, collect the same questions before and after a change. Review employees and guests separately alongside room use.")
        csv_download(filtered, "Download sample feedback", "neat-feedback-SAMPLE.csv", "feedback_export")
        with st.expander("About these samples and a future live pilot"):
            st.write("Samples use each room's recorded weekdays and office hours, going back to its first available observations. Ratings and comments are generated independently of sensor readings. Missing source dates stay empty. Choose Full history above to see the whole available period.")
            st.write("A live pilot would use the same room, audience, space rating, equipment rating, optional issue and comment fields. The Frame would submit to an authenticated service with persistent storage, and the dashboard would read that service separately from sensor data.")
            st.caption("Before a pilot: confirm the Frame's custom web app setup, assign each device to a room, choose a response store and IT-help destination, and agree access and retention. Reset the screen between visitors. No real feedback or IT-help integration is connected yet.")
    with frame_tab:
        room_key = choose_room(ctx, "Room shown on the Frame")
        room = ctx["inventory"].set_index("Room key", drop=False).loc[room_key]
        left, right = st.columns([1, 1.15], gap="large")
        with left:
            portrait_survey(room)
        with right:
            st.subheader("Built around a few taps")
            st.write("Choose Neat employee or customer / guest, rate the space and equipment, then optionally flag something to improve.")
            st.page_link("pages/Frame.py", label="Open the portrait screen", icon=":material/open_in_full:")
            st.caption("Portrait web prototype for Neat Frame. Hardware deployment and touch behaviour still need a device test.")
            session_results()
    u.footer()


def frame_page():
    st.set_page_config(page_title="Neat | Frame feedback demo", page_icon=str(u.ROOT / "assets/neat-logo.svg"), layout="wide", initial_sidebar_state="collapsed")
    st.html(u.brand_css())
    styles()
    st.html('<style>[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none}.stMainBlockContainer{max-width:560px;padding:1rem 1.4rem}.st-key-frame_screen{margin-top:0}</style>')
    data, _, _ = load()
    inventory = a.inventory(data)
    inventory = inventory[inventory.Capacity.gt(0)]
    if not st.session_state.get("demo_mode", False):
        inventory = inventory[inventory.Location.isin(["London EC", "Oslo EC"])]
    rooms = sorted(inventory["Room key"].tolist())
    requested = st.query_params.get("room", st.session_state.get("selected_room"))
    if requested not in rooms:
        if not rooms:
            st.info("No rooms available for this demo.")
            return
        requested = st.selectbox("Room for this demonstration", rooms)
    st.session_state["selected_room"] = requested
    st.query_params["room"] = requested
    portrait_survey(inventory.set_index("Room key", drop=False).loc[requested])
    st.page_link("pages/Feedback.py", label="Back to feedback results", icon=":material/arrow_back:")
