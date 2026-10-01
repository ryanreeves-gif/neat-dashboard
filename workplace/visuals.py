"""Visual summaries of observed evidence; unknown data stays unknown."""
from __future__ import annotations

from html import escape
from uuid import uuid4
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from workplace import ui as u

BLUE = "#557BC2"
PALE = "#E7EFFB"
AMBER = "#A95920"
GOLD = "#806015"
TEAL = "#397D83"
UNKNOWN = "#E7E9ED"

CSS = """<style>
/* Neat partner palette: Rain, Forest, Sunrise, Oak, Sunset and purple accents. */
.stMainBlockContainer{max-width:1480px;padding:1.8rem 1.8rem 3rem}
div[class*="st-key-card_"]{min-height:155px;padding:16px 18px;background:#EEF2F4}
div.st-key-card_util,div.st-key-card_space_util{background:#E7EDF8}
div.st-key-card_attendance,div.st-key-card_space_att{background:#EAF0ED}
div.st-key-card_reviews,div.st-key-card_space_cap{background:#F5EEDB}
div.st-key-panel_history,div.st-key-panel_heatmap{background:#EEF2F4}
div.st-key-panel_environment{background:#F2EEEA}
div.st-key-panel_environment_actions,div.st-key-panel_workflow{background:#F0EBF6;border:1px solid #E4D9EF}
div.st-key-panel_fit,div.st-key-panel_selected_fit{background:#EAF0ED}
div.st-key-panel_focus,div.st-key-panel_room_findings,div.st-key-panel_environment_findings,div.st-key-panel_insights{background:#F3F0E8}
.stButton button[kind="primary"],.stDownloadButton button[kind="primary"]{background:#5F259F;border-color:#5F259F;color:white}
.visual-legend{display:flex;flex-wrap:wrap;gap:10px 20px;margin:8px 0 14px;font-size:13px;color:#4C515C}
.visual-legend span{display:inline-flex;align-items:center;gap:7px}
.visual-legend i{display:inline-block;width:13px;height:13px;border-radius:4px;border:1px solid #D7DEE8}
.visual-strip{display:flex;height:16px;border-radius:9px;overflow:hidden;background:#E7E9ED;margin:10px 0 12px}
.visual-strip span{height:100%;min-width:0}
.visual-strip .unobserved{background:repeating-linear-gradient(135deg,#E7E9ED,#E7E9ED 5px,#F6F7F8 5px,#F6F7F8 9px)}
.visual-labels{display:flex;flex-wrap:wrap;justify-content:space-between;gap:10px;font-size:13px;color:#4C515C}
.visual-labels strong{color:#333}
.visual-roomfit{margin:14px 0 12px}
.roomfit-picture{display:block;width:100%;height:auto;max-width:660px;margin:4px auto 8px}
.roomfit-legend{display:flex;justify-content:center;gap:10px 22px;flex-wrap:wrap;font-size:12px;color:#4C515C;margin:2px 0 14px}
.roomfit-legend span{display:inline-flex;align-items:center;gap:7px}
.roomfit-legend i{width:10px;height:10px;border-radius:50%;display:inline-block}
.roomfit-busy{border-top:1px solid #CEDBD5;padding-top:12px;color:#4C515C;font-size:13px;line-height:1.5}
.roomfit-busy strong{color:#333}
.roomfit-note{color:#687383;font-size:11px;line-height:1.5;margin-top:6px}
div[class*="st-key-finding_"]{border:1px solid #E3E8EF;border-radius:15px;padding:16px;background:#FFF;height:100%}
div[class*="st-key-finding_"]:has(.finding-warm){background:#F7EDE9;border-top:4px solid #D69B8C}
div[class*="st-key-finding_"]:has(.finding-light){background:#FAF5E7;border-top:4px solid #DBC684}
div[class*="st-key-finding_"]:has(.finding-fit){background:#EBF0F5;border-top:4px solid #93ABB3}
.finding-label{font-size:14px;font-weight:700;display:flex;align-items:center;gap:8px;min-height:24px}
.finding-label .dot{height:10px;width:10px;border-radius:50%;display:inline-block;flex-shrink:0}
.finding-room{font-weight:700;font-size:18px;line-height:1.3;margin:10px 0 3px;min-height:46px;overflow-wrap:anywhere}
.finding-location{font-size:12px;color:#687383;min-height:18px}
.finding-value{font-size:32px;font-weight:700;letter-spacing:-.5px;margin:12px 0 0;line-height:1.15}
.finding-value small{font-size:14px;font-weight:400;letter-spacing:0;color:#4C515C}
.finding-track{height:7px;border-radius:5px;background:#EDF0F4;margin:12px 0 14px;overflow:hidden}
.finding-track div{height:100%;border-radius:5px}
.sensor-value{font-size:36px;font-weight:700;letter-spacing:-1px;line-height:1.2;margin-top:7px}
.sensor-value small{font-size:17px;font-weight:400;letter-spacing:0;margin-left:4px}
.sensor-status{font-size:12px;min-height:34px;line-height:1.4;margin-top:7px}
.sensor-spark{height:40px;width:100%;margin-top:7px;display:block}
div[class*="st-key-sensor_tile_"]{background:white;border:1px solid #E3E8EF;border-radius:14px;padding:12px 15px}
div.st-key-sensor_tile_Temperature{background:#F8EDE9;border-color:#EAD0C7}
div.st-key-sensor_tile_Humidity{background:#EAF1ED;border-color:#CDDDD4}
div.st-key-sensor_tile_Light_Level{background:#FAF4E1;border-color:#EADBA9}
div.st-key-sensor_tile_VOC{background:#EDF2F4;border-color:#D4E0E5}
.snapshot-line{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:4px 0 16px;font-size:13px;color:#4C515C}
.status-pill{display:inline-flex;align-items:center;gap:8px;padding:7px 12px;background:#EDF2FA;color:#3C5E94;border-radius:20px;font-weight:700}
.status-pill.quiet{background:#F0F2F5;color:#58616F}
.workflow-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0}
.workflow-step{display:flex;align-items:center;gap:10px;border:1px solid #E2D8EC;border-radius:12px;padding:14px;font-size:14px;line-height:1.3;background:#FBF9FD}
.workflow-step b{display:flex;justify-content:center;align-items:center;border-radius:50%;background:#EAE0F3;color:#5F259F;width:28px;height:28px;flex-shrink:0}
.workflow-step strong{font-size:14px;display:block}.workflow-step small{font-size:12px;color:#4C515C;display:block;margin-top:4px}
.stButton button,.stDownloadButton button{min-height:44px}
[data-baseweb="select"]>div{min-height:44px}
div[class*="st-key-finding_"] [data-testid="stExpander"]{border:0}
@media(max-width:1100px){.stMainBlockContainer{padding:1.5rem 1rem}.metric-value{font-size:38px}.metric-label{font-size:14px}.sensor-value{font-size:30px}div[class*="st-key-panel_"]{padding:18px}div[class*="st-key-sensor_tile_"]{padding:12px 10px}}
@media(max-width:800px){.workflow-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.finding-room{min-height:0}}
</style>"""


def styles():
    st.html(CSS)
    st.html((u.ROOT / "assets/customer.css").read_text())


def hourly_occupancy(samples, start, end, office):
    """Single room, time-weighted hourly totals including unobserved hours."""
    columns = ["Expected", "Observed", "Occupied", "Person hours", "Utilisation", "Coverage", "People"]
    if end <= start:
        return pd.DataFrame(columns=columns, index=pd.DatetimeIndex([], name="Hour"))
    index = pd.date_range(start.floor("h"), end.ceil("h"), freq="h", inclusive="left")
    if office:
        index = index[(index.dayofweek < 5) & (index.hour >= 8) & (index.hour < 19)]
    frame = pd.DataFrame(index=index)
    frame.index.name = "Hour"
    frame["Expected"] = [max(0, (min(t + pd.Timedelta(hours=1), end) - max(t, start)).total_seconds() / 3600) for t in index]
    names = {"Valid hours": "Observed", "Occupied hours": "Occupied", "Person hours": "Person hours"}
    grouped = samples.groupby(samples.Start.dt.floor("h"))[list(names)].sum().rename(columns=names)
    frame = frame.join(grouped).fillna({"Observed": 0, "Occupied": 0, "Person hours": 0})
    frame["Utilisation"] = 100 * frame.Occupied / frame.Observed.replace(0, np.nan)
    frame["Coverage"] = (100 * frame.Observed / frame.Expected.replace(0, np.nan)).clip(upper=100)
    frame["People"] = frame["Person hours"] / frame.Observed.replace(0, np.nan)
    return frame


def hourly_sensor(samples, signal, start, end, office):
    """Weight each valid environmental observation by its supported interval."""
    grid = hourly_occupancy(samples, start, end, office)
    valid = samples[signal].notna() & samples["Device Status"].isin(["Online", "Unreported"])
    selected = samples.loc[valid].copy()
    selected["Weighted"] = selected[signal] * selected.Hours
    grouped = selected.groupby(selected.Start.dt.floor("h"))[["Weighted", "Hours"]].sum()
    return (grouped.Weighted / grouped.Hours.replace(0, np.nan)).reindex(grid.index)


def period_balance(hourly):
    expected = float(hourly.Expected.sum())
    observed = float(hourly.Observed.sum())
    occupied = float(hourly.Occupied.sum())
    return occupied, max(0, observed - occupied), max(0, expected - observed)


def balance_strip(hourly):
    values = period_balance(hourly)
    total = sum(values)
    if not total:
        return
    labels = ["Occupied", "Observed empty", "Unobserved"]
    colors = [BLUE, PALE, UNKNOWN]
    pieces = ''.join(f'<span class="{"unobserved" if i == 2 else ""}" style="width:{100*v/total:.4f}%;background-color:{colors[i]}"></span>' for i, v in enumerate(values))
    caption = ''.join(f'<span><strong>{escape(label)}</strong> {v:.1f} h</span>' for label, v in zip(labels, values))
    st.html(f'<div class="visual-strip" role="img" aria-label="Selected period: {escape(str(dict(zip(labels, values))))}">{pieces}</div><div class="visual-labels">{caption}</div>')


def room_capacity_svg(attendance, capacity):
    """One silhouette per recorded seat, with exact fractional average fills."""
    seats = int(capacity)
    if seats < 1 or seats != capacity or not np.isfinite(attendance) or attendance < 0:
        raise ValueError("Room illustration requires whole seats and valid attendance.")
    uid = "roomfit-" + uuid4().hex
    # Alternate across the table so a small group feels naturally seated.
    ends = 2 if seats >= 6 else 0
    side_count = seats - ends
    top_count, bottom_count = (side_count + 1) // 2, side_count // 2
    wide = max(560, top_count * 56 + 160)
    table_left, table_right = 78, wide - 78
    positions = []
    for i in range(top_count):
        x = table_left + (i + .5) * (table_right - table_left) / top_count
        positions.append((x, 40))
        if i < bottom_count:
            bx = table_left + (i + .5) * (table_right - table_left) / bottom_count
            positions.append((bx, 226))
    if ends:
        positions.extend([(32, 133), (wide - 32, 133)])
    silhouette = '<circle cx="0" cy="-12" r="9"/><path d="M-8 1 Q-15 2 -17 10 L-20 22 Q-21 27 -15 27 H15 Q21 27 20 22 L17 10 Q15 2 8 1 Z"/>'
    people = []
    for i, (x, y) in enumerate(positions):
        filled = min(1.0, max(0.0, float(attendance) - i))
        shade = BLUE if filled == 1 else "#BDC8C5"
        person = f'<g fill="{shade}">{silhouette}</g>'
        if 0 < filled < 1:
            clip = f"{uid}-{i}"
            # Horizontal clipping preserves the decimal, e.g. 2.7 = 2 + 70%.
            person += (f'<defs><clipPath id="{clip}" clipPathUnits="userSpaceOnUse">'
                       f'<rect x="-21" y="-24" width="{42 * filled:.6f}" height="55"/>'
                       f'</clipPath></defs><g fill="{BLUE}" clip-path="url(#{clip})">{silhouette}</g>')
        people.append(f'<g class="roomfit-person" data-filled="{filled:.6f}" transform="translate({x:.2f} {y})">{person}</g>')
    description = (f"Illustrative meeting table with {seats} seats. Average attendance while occupied: "
                   f"{attendance:.1f} people. Blue represents average attendance; grey represents remaining capacity.")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" class="roomfit-picture" viewBox="0 0 {wide} 270" '
            f'role="img" aria-labelledby="{uid}-title"><title id="{uid}-title">{escape(description)}</title>'
            f'<rect x="{table_left}" y="92" width="{table_right-table_left}" height="102" rx="38" fill="#D9E3DE"/>'
            f'<rect x="{table_left}" y="86" width="{table_right-table_left}" height="102" rx="38" fill="#FFFFFF" stroke="#D6E1DB" stroke-width="1.5"/>'
            f'<text x="{wide/2:g}" y="132" text-anchor="middle" font-family="Arial,sans-serif" font-size="29" font-weight="700" fill="#333333">{seats} seats</text>'
            f'<text x="{wide/2:g}" y="154" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" fill="#687383">ROOM CAPACITY</text>'
            + ''.join(people) + '</svg>')


def capacity_bar(attendance, capacity, p90):
    """Render the room illustration; retain the callable used by both pages."""
    if (pd.isna(capacity) or pd.isna(attendance) or not np.isfinite(capacity)
            or not np.isfinite(attendance) or capacity <= 0 or attendance < 0):
        st.caption("Occupied observations and recorded capacity are needed to show room fit.")
        return
    if int(capacity) != capacity:
        st.caption("A whole-number room capacity is needed to draw one person per seat.")
        return
    graphic = room_capacity_svg(attendance, capacity)
    busy = (f'90% of occupied time: <strong>{u.fmt(p90)} people or fewer</strong>.'
            if pd.notna(p90) and np.isfinite(p90) else 'Busy-period attendance is unavailable.')
    note = 'Illustrative layout. Part-filled people show the fractional average.'
    if attendance > capacity:
        note += ' Average attendance exceeds recorded capacity; review the room metadata.'
    st.html(f'<div class="visual-roomfit"><div class="visual-labels">'
            f'<span><strong>{attendance:.1f}</strong> typical people</span>'
            f'<span>Average while occupied</span></div></div>')
    # st.html uses an HTML-only sanitizer and removes inline SVG elements.
    # The native image component supports SVG as an encoded image source.
    with st.container(horizontal=True, horizontal_alignment="center"):
        st.image(graphic, width=660)
    st.html(f'<div class="visual-roomfit"><div class="roomfit-legend"><span><i style="background:{BLUE}"></i>Typical attendance</span>'
            f'<span><i style="background:#BDC8C5"></i>Remaining capacity</span></div>'
            f'<div class="roomfit-busy">{busy}</div><div class="roomfit-note">{note}</div></div>')


def occupancy_figure(hourly, typical=False, capacity=None):
    """Average people / recorded seats; observed empty time stays in the mean."""
    if (hourly.empty or capacity is None or pd.isna(capacity)
            or not np.isfinite(capacity) or capacity <= 0):
        return go.Figure()
    seats = float(capacity)
    hour_numbers = sorted(hourly.index.hour.unique())
    if typical:
        grouped = hourly.groupby([hourly.index.dayofweek, hourly.index.hour])[["Expected", "Observed", "Occupied", "Person hours"]].sum()
        rows = sorted(hourly.index.dayofweek.unique())
        labels = [["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][int(d)] for d in rows]
    else:
        grouped = hourly.groupby([hourly.index.normalize(), hourly.index.hour])[["Expected", "Observed", "Occupied", "Person hours"]].sum()
        rows = sorted(hourly.index.normalize().unique())
        labels = [d.strftime("%a %d %b") for d in rows]
    # Reserve a small grey band below zero exclusively for unknown cells.
    z = np.full((len(rows), len(hour_numbers)), -1.0)
    texts = np.full(z.shape, "?", dtype=object)
    hover = np.empty(z.shape, dtype=object)
    for i, day in enumerate(rows):
        for j, hour in enumerate(hour_numbers):
            index = (day, hour)
            if index not in grouped.index:
                texts[i, j] = ""
                hover[i, j] = "Outside selected period"
                continue
            cell = grouped.loc[index]
            coverage = 100 * cell.Observed / cell.Expected if cell.Expected else 0
            people = cell["Person hours"] / cell.Observed if cell.Observed else np.nan
            capacity_used = 100 * people / seats
            if coverage >= 50 and pd.notna(people):
                z[i, j] = capacity_used
                number = "<0.1" if 0 < capacity_used < .1 else f"{capacity_used:.1f}".removesuffix(".0")
                texts[i, j] = number + "%" + ("*" if coverage < 90 else "")
            average_label = (f"Average capacity used: {capacity_used:.1f}%<br>Average people: {people:.2f} / {seats:g} seats" if coverage >= 50 and pd.notna(people)
                             else "Average unavailable: limited / missing observations")
            hover[i, j] = (f"{average_label}<br>Includes observed empty periods"
                            f"<br>Coverage: {coverage:.0f}%<br>Observed: {cell.Observed:.2f} / {cell.Expected:.2f} h")
    scale = [[0, UNKNOWN], [.009, UNKNOWN], [.0099, PALE], [.25, "#C4D5F2"], [.50, "#9BB8E6"], [.75, "#7596CE"], [1, "#557BC2"]]
    fig = go.Figure(go.Heatmap(x=[f"{h:02d}:00" for h in hour_numbers], y=labels, z=z,
        zmin=-1, zmax=100, colorscale=scale, showscale=False, text=texts, texttemplate="%{text}",
        textfont=dict(size=14), customdata=hover, xgap=5, ygap=5,
        hovertemplate="%{y} \u00b7 %{x}<br>%{customdata}<extra></extra>"))
    u.plot_style(fig, max(235, 62 + len(rows) * 38))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=13), fixedrange=True)
    fig.update_xaxes(side="top", tickfont=dict(size=12), fixedrange=True)
    fig.update_layout(margin=dict(l=5, r=6, t=30, b=5), meta={"metric": "average_capacity_used", "capacity": seats})
    return fig


def occupancy_pattern(ctx, room, key):
    samples = ctx["samples"][ctx["samples"]["Room key"] == room]
    hourly = hourly_occupancy(samples, ctx["start"], ctx["end"], ctx["office"])
    if hourly.empty:
        st.info("No operating hours in this selection.")
        return
    balance_strip(hourly)
    span = (ctx["end"] - ctx["start"]).days
    mode = st.radio("Pattern view", ["By date", "Typical week"], index=1 if span > 14 else 0,
                    horizontal=True, key=f"{key}_mode", label_visibility="collapsed")
    show = hourly
    if mode == "By date":
        dates = sorted(hourly.index.normalize().unique())
        windows = [dates[i:i+14] for i in range(0, len(dates), 14)]
        if len(windows) > 1:
            index = st.selectbox("Days to display", range(len(windows)), index=len(windows)-1,
                format_func=lambda i: f"{windows[i][0]:%d %b %Y} to {windows[i][-1]:%d %b %Y}", key=f"{key}_window")
            show = hourly[hourly.index.normalize().isin(windows[index])]
    room_metadata = ctx["inventory"][ctx["inventory"]["Room key"] == room]
    capacity = room_metadata.iloc[0].Capacity if not room_metadata.empty else None
    if capacity is None or pd.isna(capacity) or not np.isfinite(capacity) or capacity <= 0:
        st.info("Recorded room capacity is needed to show average capacity used.")
        return
    st.write("**Average capacity used**")
    st.caption(f"Each block = one hour. Average people / {capacity:g} seats, including observed empty periods.")
    fig = occupancy_figure(show, mode == "Typical week", capacity)
    st.plotly_chart(fig, width="stretch",
                    config={"displayModeBar": False, "scrollZoom": False}, key=f"{key}_map")
    st.html(f'<div class="visual-legend"><span><i style="background:{PALE}"></i>0% capacity</span><span><i style="background:#9BB8E6"></i>50% capacity</span><span><i style="background:{BLUE}"></i>100% capacity</span><span><i style="background:{UNKNOWN}"></i>? limited / missing data</span><span>* partial coverage</span></div>')
    with st.expander("Read the pattern and inspect exact hours"):
        st.write("Average capacity used = time-weighted average people / recorded room capacity. An average of 3.7 people in a 10-seat room gives 37%. Six people for half an observed hour and an empty room for the other half gives an average of three people. Missing time is excluded, rather than counted as empty. A question mark means less than 50% of that hour was observed; an asterisk marks 50-89% coverage.")
        st.caption("The colour scale is 0-100% of recorded seats. Values above 100% retain their number and use the darkest blue; review the people counts and room capacity. The room illustration shows average attendance only while occupied, so its number can differ from an hourly average that includes empty periods.")
        st.caption("Typical week combines the selected dates using observed hours as weights. The bar above always covers the full selected period. Times follow the source clock.")
        table = hourly[["Observed", "Occupied", "Utilisation", "Coverage", "People"]].copy().round(1)
        table.columns = ["Observed hours", "Hours with people", "Time in use (%)", "Coverage %", "Average people"]
        table["Average capacity used (%)"] = (100 * hourly.People / capacity).round(1)
        st.dataframe(table, width="stretch")


def finding_summary(row, largest, show_room=True):
    kind = row.Kind
    color = {"warm": AMBER, "light": GOLD, "fit": BLUE}.get(kind, BLUE)
    label = {"warm": "Warm + empty", "light": "Bright + empty", "fit": "Room fit to review"}.get(kind, row.Finding)
    hours = float(row["Evidence hours"])
    width = 100 * hours / largest if largest else 0
    room = f'<div class="finding-room">{escape(str(row["Room"]))}</div><div class="finding-location">{escape(str(row.Location))}</div>' if show_room else ''
    st.html(f'<div class="finding-label finding-{escape(kind)}" style="color:{color}"><span class="dot" style="background:{color}"></span>{escape(label)}</div>{room}<div class="finding-value">{hours:.1f}<small> observed h</small></div><div class="finding-track" aria-label="{hours:.1f} hours of evidence"><div style="width:{width:.3f}%;background:{color}"></div></div>')


def sparkline(series, color):
    """Split paths at gaps; one isolated reading remains visible."""
    values = list(series)
    finite = [float(v) for v in values if pd.notna(v)]
    if not finite:
        return '<svg class="sensor-spark" viewBox="0 0 180 40" role="img" aria-label="No valid observations"><path d="M0 23H180" stroke="#E1E5EB" stroke-dasharray="3 4"/></svg>'
    low, high = min(finite), max(finite)
    spread = max(high - low, .1)
    paths, current, circles = [], [], []
    for i, value in enumerate(values):
        if pd.isna(value):
            if current: paths.append(current); current = []
            continue
        x = 3 + 174 * i / max(1, len(values)-1)
        y = 20 if high == low else 34 - 28 * (float(value)-low)/spread
        current.append((x, y))
    if current: paths.append(current)
    for points in paths:
        if len(points) == 1:
            x, y = points[0]
            circles.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{color}"/>')
        else:
            shape = ' '.join(f'{"M" if i == 0 else "L"}{x:.1f} {y:.1f}' for i, (x,y) in enumerate(points))
            circles.append(f'<path d="{shape}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>')
    return '<svg class="sensor-spark" viewBox="0 0 180 40" role="img" aria-label="Hourly trend in selected period">' + ''.join(circles) + '</svg>'


def set_signal(signal):
    st.session_state["environment_signal"] = signal


def condition_tiles(ctx, room):
    latest = ctx["inventory"].set_index("Room key").loc[room]
    reporting = latest["Device Status"] in ("Online", "Unreported")
    occupancy = latest.Occupancy if reporting else np.nan
    badge = "Occupancy unknown" if pd.isna(occupancy) else ("Empty" if occupancy == 0 else f"Occupied \u00b7 {occupancy:g} people")
    quiet = pd.isna(occupancy) or occupancy == 0
    st.html(f'<div class="snapshot-line"><span class="status-pill {"quiet" if quiet else ""}">{escape(badge)}</span><span>Latest selected record \u00b7 {latest.Timestamp:%d %b %Y %H:%M}</span></div>')
    current = st.session_state.get("environment_signal", "Temperature")
    columns = st.columns(4)
    samples = ctx["samples"][ctx["samples"]["Room key"] == room]
    for column, (name, title, unit, icon) in zip(columns, [
        ("Temperature", "Temperature", "\u00b0C", "thermostat"), ("Humidity", "Humidity", "%", "humidity_percentage"),
        ("Light Level", "Light level", "lx", "light_mode"), ("VOC", "Air quality", "source units", "air")]):
        value = latest.get(name) if reporting else np.nan
        color = TEAL if name == "Humidity" else BLUE
        if pd.isna(value):
            status, color = "No valid reading", "#687383"
        elif name in ("Temperature", "Light Level"):
            threshold = ctx["thresholds"]["warm" if name == "Temperature" else "bright"]
            status = f"{'Above' if value > threshold else 'At / below'} {threshold:g} {unit} review level"
            color = (AMBER if name == "Temperature" else GOLD) if value > threshold else BLUE
        elif name == "Humidity":
            status = "Relative humidity"
        else:
            status, color = "VOC \u00b7 units to validate", "#687383"
        with column, st.container(key=f"sensor_tile_{name.replace(' ', '_')}"):
            st.button(title, key=f"sensor_select_{name}", icon=f":material/{icon}:",
                      type="primary" if current == name else "secondary", width="stretch",
                      on_click=set_signal, args=(name,))
            series = hourly_sensor(samples, name, ctx["start"], ctx["end"], ctx["office"])
            series = series.reindex(pd.date_range(ctx["start"].floor("h"), ctx["end"].floor("h"), freq="h"))
            display_unit = "" if name == "VOC" or pd.isna(value) else unit
            st.html(f'<div class="sensor-value" style="color:{color}">{escape(u.fmt(value, digits=1 if name == "Temperature" else 0))}<small>{escape(display_unit)}</small></div><div class="sensor-status" style="color:{color}">{escape(status)}</div>')
            st.image(sparkline(series, color), width="stretch")
    st.caption("Select a card heading to explore its trend. Mini charts use individual scales.")
    return current


def workflow_map(events):
    steps = [("Sensor evidence", "Neat Pulse + Streamlit"), ("JSON request", "Authenticated HTTPS"),
             ("Policy checks", "ServiceNow workflow"), ("BMS command", "e.g. Tridium Niagara / BACnet"),
             ("Equipment feedback", "Acceptance + state readback"), ("Verify + restore", "Readings + normal schedule")]
    st.caption("Proposed sequence")
    st.html('<div class="workflow-grid">' + ''.join(f'<div class="workflow-step"><b>{i}</b><span><strong>{escape(name)}</strong><small>{escape(detail)}</small></span></div>' for i, (name, detail) in enumerate(steps[:len(events)], 1)) + '</div>')
