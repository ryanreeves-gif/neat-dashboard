from __future__ import annotations
import base64
from datetime import timedelta
from math import ceil
from html import escape
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
from workplace import analytics as a
from workplace.executive import evidence_summary
from workplace.data import load, fetch
from workplace.help import HELP, WHY

ROOT = Path(__file__).resolve().parent.parent
BLUE = "#6A87D0"
INK = "#333333"
MUTED = "#4C515C"
FONT = "MaisonNeue, Helvetica Neue, Arial, sans-serif"


@st.cache_data
def brand_css():
    book = base64.b64encode((ROOT / "assets/MaisonNeue-Book.woff2").read_bytes()).decode()
    bold = base64.b64encode((ROOT / "assets/MaisonNeue-Bold.woff2").read_bytes()).decode()
    return f"""<style>
    @font-face{{font-family:MaisonNeue;src:url(data:font/woff2;base64,{book}) format('woff2');font-weight:400;font-display:swap;}}
    @font-face{{font-family:MaisonNeue;src:url(data:font/woff2;base64,{bold}) format('woff2');font-weight:700;font-display:swap;}}
    </style>""" + (ROOT / "assets/theme.css").read_text() + (ROOT / "assets/customer.css").read_text()


def shell(active, title, subtitle, briefing=False):
    from workplace.customer import PURPOSE
    st.set_page_config(page_title=f"Neat | {active}", page_icon=str(ROOT / "assets/neat-logo.svg"), layout="wide")
    st.html(brand_css())
    with st.sidebar:
        logo = base64.b64encode((ROOT / "assets/neat-logo.svg").read_bytes()).decode()
        st.html(f'<div class="brand"><img src="data:image/svg+xml;base64,{logo}" alt="Neat"/><p>Workplace intelligence</p></div>')
        presentation = st.toggle("Presentation view", **field_state("presentation_mode", True),
                                 help="Four compact chapters for the webinar. Switch off for the full dashboard.")
        groups = [
            ("Understand", [("app.py", "Overview", "dashboard"), ("pages/Spaces.py", "Spaces", "meeting_room"),
                            ("pages/Feedback.py", "Feedback", "sentiment_satisfied"), ("pages/Environment.py", "Environment", "thermostat")]),
            ("Improve", [("pages/Insights.py", "Opportunities", "insights"), ("pages/Scenarios.py", "Scenarios", "compare_arrows"),
                         ("pages/Value.py", "Value & ROI", "finance_mode")]),
            ("Operate", [("pages/Administration.py", "Operations", "tune"), ("pages/AI_Search.py", "Ask the data", "search")])]
        if presentation:
            st.html('<div class="nav-group">THE TEN-MINUTE STORY</div>')
            for path, label, icon in [("app.py", "01 · Current state", "dashboard"),
                                      ("pages/Spaces.py", "02 · Room fit", "meeting_room"),
                                      ("pages/Feedback.py", "03 · Experience", "sentiment_satisfied"),
                                      ("pages/Environment.py", "04 · Improve", "bolt")]:
                st.page_link(path, label=label, icon=f":material/{icon}:", width="stretch")
            with st.expander("Explore the full analysis"):
                for _, links in groups:
                    for path, label, icon in links:
                        if path in ["app.py", "pages/Spaces.py", "pages/Feedback.py", "pages/Environment.py"]:
                            continue
                        st.page_link(path, label=label, icon=f":material/{icon}:", width="stretch")
                st.caption("Switch Presentation view off for the detailed version of every chapter.")
            with st.popover("Presenter guide", icon=":material/co_present:", width="stretch"):
                st.markdown("**A ten-minute story**")
                st.write("**0:00–3:00 · The current state.** Show the room map and the separate usage and sentiment leaders. Open Improvement choices: which rooms need a controls review, a layout review, or both?")
                st.write("**3:00–5:00 · The right space.** Use one room, its automatic peer and the visual layout comparison. Ask what the room is for before changing its size.")
                st.write("**5:00–7:00 · The experience.** Contrast employees and guests, then demonstrate a few taps on the portrait survey.")
                st.write("**7:00–10:00 · The next move.** Play the simulated Pulse → ServiceNow → BMS workflow. Close on one pilot, an owner and a review date.")
                st.caption("Pulse supplies observations. Feedback is synthetic, financial values are assumptions and building controls are simulated. None measures whether a commute is worthwhile by itself.")
        else:
            for group, links in groups:
                st.html(f'<div class="nav-group">{group}</div>')
                for path, label, icon in links:
                    st.page_link(path, label=label, icon=f":material/{icon}:", width="stretch")
        with st.expander("Data source"):
            st.caption("Published telemetry CSV · cached for 10 minutes")
            st.toggle("Use demonstration data", **field_state("demo_mode", False))
            if st.button("Refresh observations", width="stretch"):
                fetch.clear()
                analysis.clear()
                st.rerun()
    if briefing:
        st.html((ROOT / "assets/briefing.css").read_text())
    st.html(f'<div class="eyebrow">{escape(active.upper())} / {escape(PURPOSE.get(active, "").upper())}</div><h1 class="hero">{escape(title)}</h1><p class="subtitle">{escape(subtitle)}</p>')


def explain(key, widget_key=None):
    title, hint, calculation, caveat = HELP[key]
    with st.popover("Info", icon=":material/info:", help=f"{title}: {hint}", type="tertiary", width=68,
                    key=widget_key or f"help_{key}"):
        st.markdown(f"**{title}**")
        st.write(hint)
        st.markdown("**Why it matters**")
        st.write(WHY[key])
        st.markdown("**How it works**")
        st.write(calculation)
        st.markdown("**Keep in mind**")
        st.write(caveat)


def section(title, help_key, suffix=""):
    left, right = st.columns([12, 1.5], vertical_alignment="center")
    with left:
        st.html(f'<h2 class="section-title">{escape(title)}</h2>')
    with right:
        explain(help_key, f"help_{help_key}_{suffix}")


def metric(label, value, detail, help_key, key, delta=None):
    with st.container(key=f"card_{key}", border=False):
        left, right = st.columns([5, 1.8], vertical_alignment="center")
        with left:
            st.html(f'<div class="metric-label">{escape(label)}</div>')
        with right:
            explain(help_key, f"metric_help_{key}")
        st.html(f'<div class="metric-value">{escape(value)}</div><div class="metric-detail">{escape(detail)}</div>' +
                (f'<div class="metric-comparison">{escape(delta)}</div>' if delta else ''))


def fmt(value, suffix="", digits=0):
    return "—" if pd.isna(value) else f"{value:,.{digits}f}{suffix}"


def remember(name):
    st.session_state[name] = st.session_state["_" + name]


def field_state(name, default):
    st.session_state["_" + name] = st.session_state.get(name, default)
    return {"key": "_" + name, "on_change": remember, "args": (name,)}


@st.cache_data(max_entries=12, show_spinner=False)
def analysis(_data, fetched, rooms, start, end, office, warm, bright, minimum):
    data = _data[_data["Room key"].isin(rooms)]
    samples = a.intervals(data, start, end, office)
    inv = a.inventory(data[data.Timestamp <= end])
    inv = inv[inv["Room key"].isin(rooms)]
    hours = a.window_hours(start, end, office)
    stats = a.room_statistics(samples, inv, hours)
    summary = a.summarise(samples, hours, len(inv))
    issues = a.findings(samples, stats, warm, bright, minimum)
    # Align clocks and preserve a partial final day in the comparison period.
    shift = pd.Timedelta(days=max(1, ceil((end - start).total_seconds() / 86400)))
    previous_end = end - shift
    previous_start = start - shift
    prior = a.intervals(data, previous_start, previous_end, office)
    previous = a.summarise(prior, a.window_hours(previous_start, previous_end, office), len(inv))
    return samples, inv, stats, summary, issues, previous


def context(show_evidence=True, compact=False, sidebar_details=False):
    data, quality, fetched = load()
    available = set(data.Location.unique())
    locations = (sorted(available) if st.session_state.get("demo_mode", False)
                 else [name for name in ("London EC", "Oslo EC") if name in available])
    if not locations:
        st.info("No room observations are available for London EC or Oslo EC.")
        st.stop()
    default = ["London EC"] if "London EC" in locations else locations[:1]
    previous_locations = st.session_state.get("locations", default)
    selected_locations = [x for x in previous_locations if x in locations]
    st.session_state["locations"] = default if previous_locations and not selected_locations else selected_locations
    c1, c2, c3, c4 = ([st.container() for _ in range(4)] if compact else
                       st.columns([2.5, 2.8, 2.3, 2.4], vertical_alignment="bottom"))
    with c1:
        selected = st.multiselect("Locations", locations, placeholder="Choose locations", **field_state("locations", default))
    with c3:
        preset = st.selectbox("Date range", ["Last 7 days", "Last 30 days", "Last 90 days", "Full history", "Custom dates"], **field_state("preset", "Last 7 days"))
    with c4:
        mode = st.selectbox("Operating hours", ["Office hours", "All hours"], **field_state("hours", "Office hours"))
    if not selected:
        st.info("Select at least one location to explore its rooms.")
        st.stop()
    scope = data[data.Location.isin(selected)].copy()
    last = scope.Timestamp.max()
    first = scope.Timestamp.min()
    end_date = last.date()
    days = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}
    start_date = end_date - timedelta(days=days[preset] - 1) if preset in days else first.date()
    if preset == "Custom dates":
        saved_dates = st.session_state.get("custom_dates", (max(first.date(), end_date-timedelta(days=6)), end_date))
        if len(saved_dates) == 2:
            st.session_state["custom_dates"] = tuple(max(first.date(), min(end_date, d)) for d in saved_dates)
        dates = st.date_input("Custom date range", min_value=first.date(), max_value=end_date,
                              **field_state("custom_dates", (max(first.date(), end_date-timedelta(days=6)), end_date)))
        if len(dates) != 2:
            st.info("Choose both a start date and an end date.")
            st.stop()
        start_date, end_date = dates
    start = pd.Timestamp(start_date)
    # No forward projection past the last observation in this selected feed.
    end = min(pd.Timestamp(end_date) + pd.Timedelta(days=1), last)
    inv = a.inventory(scope[scope.Timestamp <= end])
    inv = inv[inv.Timestamp >= start]
    if sidebar_details:
        with st.sidebar.expander("Data & thresholds"):
            col1, col2, col3, col4 = [st.container() for _ in range(4)]
    else:
        col1, col2, col3, col4 = ([st.container() for _ in range(4)] if compact else
                                  st.columns([5, 2.5, 1.7, 1.9], vertical_alignment="center"))
    with col4:
        with st.popover("More filters", icon=":material/tune:", width="stretch"):
            include = st.toggle("Include unclassified and non-meeting assets", **field_state("include_assets", False))
            st.caption("Evidence thresholds · investigation settings")
            warm = st.number_input("Warm empty room (°C)", min_value=10.0, max_value=40.0, step=.5, **field_state("warm", 22.0))
            bright = st.number_input("Bright empty room (lux)", min_value=1.0, max_value=10000.0, step=10.0, **field_state("bright", 50.0))
            minimum = st.number_input("Minimum repeated evidence (hours)", min_value=.25, max_value=100.0, step=.25, **field_state("min_hours", 1.0))
            st.caption("Office hours: Mon–Fri, 08:00–19:00 in the source's recorded clock. No per-location timezone mapping is supplied.")
    eligible = inv if include else inv[inv.Capacity.gt(0)]
    opts = sorted(eligible["Room key"].tolist())
    st.session_state["room_filter"] = [x for x in st.session_state.get("room_filter", []) if x in opts]
    with c2:
        chosen = st.multiselect("Rooms", opts, placeholder="All rooms",
                                help="Filter the dashboard to one or more rooms. Clear the selection to show all rooms in the selected locations.",
                                **field_state("room_filter", []))
    room_keys = tuple(chosen or opts)
    if not room_keys or end <= start:
        st.info("No meeting-room observations in this scope. Adjust the dates or include unclassified assets under More filters.")
        st.stop()
    samples, inv, stats, summary, issues, previous = analysis(scope, fetched, room_keys, start, end, mode == "Office hours", warm, bright, minimum)
    ctx = dict(data=scope, all_data=data, samples=samples, inventory=inv, stats=stats, summary=summary, issues=issues, previous=previous,
               start=start, end=end, office=mode == "Office hours", quality=quality, fetched=fetched,
               excluded=len(a.inventory(scope[scope.Timestamp <= end]))-len(inv), thresholds=dict(warm=warm, bright=bright, minimum=minimum),
               demo=bool(st.session_state.get("demo_mode", False)),
               latest_source=scope.loc[scope["Room key"].isin(room_keys), "Timestamp"].max())
    with col1:
        st.html(f'<div class="scope-note">{start:%d %b} – {end:%d %b %Y, %H:%M} · Recorded source time · {len(inv)} rooms</div>')
    with col2:
        st.html(f'<div class="scope-note">Occupancy coverage: <strong>{fmt(summary["coverage"], "%")}</strong></div>')
    with col3:
        with st.popover("Data quality", icon=":material/info:", help=HELP["coverage"][1], width="stretch"):
            st.write(HELP["coverage"][2])
            st.caption(HELP["coverage"][3])
            st.write(f"Observed: {summary['valid_hours']:,.1f} room-hours / scheduled: {summary['expected_hours']:,.1f} room-hours")
            st.write(f"Latest source record in these locations: {last:%d %b %Y %H:%M}")
            st.caption(f"CSV fetched {fetched:%d %b %Y %H:%M} (server clock). Date parser: {quality['date_order']}.")
            st.caption("Comparison uses the preceding date window with the same elapsed length and clock times. A headline change appears only when both periods have at least 70% occupancy coverage.")
            st.write(f"Invalid timestamps removed: {quality['invalid_dates']:,}. Duplicate room/timestamp rows removed: {quality['duplicates']:,}.")
            st.caption("Room capacity comes from available metadata; unknown values are never assumed to be four seats. Retired assets and room aliases should be resolved in the collector.")
            if quality["status_unreported"]:
                st.warning("This source does not report device status; coverage cannot exclude offline devices.")
    if show_evidence:
        evidence_banner(ctx)
    return ctx


def evidence_banner(ctx):
    q, s = evidence_summary(ctx), ctx["summary"]
    latest = "Unknown" if pd.isna(q["latest"]) else f"{q['latest']:%d %b %Y, %H:%M}"
    details = "Generated sample data — not customer evidence." if ctx["demo"] else "Missing readings stay unknown. Coverage measures completeness, not accuracy."
    if q["status_unreported"]:
        details += " Some source records do not report device status."
    st.html(f'''<section class="evidence-compact {escape(q['tone'])}" aria-label="Evidence quality summary">
      <span><i class="evidence-dot"></i><strong>{escape(q['label'])}</strong> · {q['rooms_ready']}/{q['rooms_total']} rooms at 70%+ coverage</span>
      <span>Latest source: {escape(latest)} · source clock</span>
      <span>{escape(details)}</span></section>''')


def plot_style(fig, height=300):
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      height=height, font=dict(family=FONT, color=MUTED, size=13),
                      margin=dict(l=5, r=10, t=10, b=8), legend_title_text="", hoverlabel=dict(bgcolor="white", font_size=13))
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="#ECEFF0", zeroline=False)
    return fig


def go_room(room_key):
    st.session_state["selected_room"] = room_key
    st.switch_page("pages/Spaces.py")


def go_scenario(room_key):
    st.session_state["selected_room"] = room_key
    st.switch_page("pages/Scenarios.py")


def footer():
    st.html('<div class="page-footer">Neat workplace intelligence · Pulse observations + labelled sample sentiment · Financial models use entered assumptions. Building controls, bookings and live surveys are not connected.</div>')
