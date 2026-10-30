"""Ryan-confirmed spatial identities, with date-scoped inventory and observations.

The picture is an illustration, not a measured plan. Display assets do not gain
meeting-room capacity, occupancy or invented survey records from their position.
"""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import base64
import re

import pandas as pd
import streamlit as st
import streamlit.components.v2 as components

from workplace import analytics as a, conclusions as x, portfolio as p, ui as u
from workplace.pilot import pilot_plan

ROOT = Path(__file__).resolve().parents[1]
SPACES = (
    dict(id="A", name="Barra", sources=("Barra",), x=22.5, y=14.5, kind="room"),
    dict(id="B", name="Harris", sources=("Harris",), x=20.6, y=32.2, kind="room"),
    dict(id="C", name="Edradour", sources=("Edradour",), x=21.2, y=41.2, kind="room"),
    dict(id="D", name="Dalmore Microsoft", sources=("Dalmore Microsoft",), x=49, y=43.1, kind="room"),
    dict(id="E", name="Longrow Lounge Board", sources=("Longrow Lounge Board 32",), x=92.1, y=69, kind="asset"),
    dict(id="F", name="Longrow", sources=("Longrow",), x=89.5, y=88.9, kind="room"),
    dict(id="G", name="Arran", sources=("Arran",), x=79, y=57.5, kind="room"),
    dict(id="H", name="Wall o’ Pads / Shelf o’ Frames", sources=("Wall o' Pads", "Shelf o' Frames"), x=58, y=72.5, kind="shared"),
    dict(id="I", name="London Envoy Kiosk", sources=("London Envoy Kiosk",), x=28, y=59.8, kind="asset"),
)


def applies(ctx):
    """Never show the London picture as an Oslo or generated demonstration office."""
    return not ctx.get("demo") and set(ctx["inventory"].Location) == {"London EC"}


def products(rows):
    """Retain repeated model counts from each source's single inventory snapshot."""
    counts = Counter()
    for _, row in rows.iterrows():
        raw = row.get("Neat Equipment")
        if pd.isna(raw):
            continue
        counts.update(c.strip().upper() for c in re.split(r"\s*\+\s*", str(raw))
                      if c.strip().upper() not in {"", "UNKNOWN", "NAN", "NONE"})
    return [dict(name=x.MODEL_NAMES.get(code, f"Unidentified model {code}"),
                 count=count, known=code in x.MODEL_NAMES)
            for code, count in sorted(counts.items(), key=lambda item: x.MODEL_NAMES.get(item[0], item[0]))]


def number(value):
    return float(value) if pd.notna(value) else None


def sensor_average(samples, key, sensor):
    rows = samples[samples["Room key"].eq(key) & samples["Device Status"].isin(["Online", "Unreported"])
                   & samples[sensor].notna() & samples.Hours.gt(0)]
    return float((rows[sensor] * rows.Hours).sum() / rows.Hours.sum()) if len(rows) else None


def map_rows(ctx, portfolio, room_filter=()):
    """Map exact source names only. No fuzzy joins, retired aliases or cross-room fills."""
    data = ctx["data"]
    window = data[data.Location.eq("London EC") & data.Timestamp.between(ctx["start"], ctx["end"])]
    inventory = a.inventory(window)
    mapped_keys = {f"London EC / {n}" for s in SPACES for n in s["sources"]}
    asset_keys = mapped_keys - set(ctx["inventory"]["Room key"])
    extra = a.intervals(data[data["Room key"].isin(asset_keys)], ctx["start"], ctx["end"], ctx["office"])
    samples = pd.concat([ctx["samples"], extra], ignore_index=True)
    stats = portfolio.set_index("Room key")
    output = []
    for spec in SPACES:
        keys = [f"London EC / {n}" for n in spec["sources"]]
        snapshots = inventory[inventory["Room key"].isin(keys)]
        allowed = not room_filter or any(key in room_filter for key in keys)
        key = keys[0] if len(keys) == 1 else None
        row = stats.loc[key] if allowed and key in stats.index and spec["kind"] == "room" else None
        eligible_use = row is not None and bool(row["Usage eligible"])
        eligible_rating = row is not None and bool(row["Sentiment eligible"])
        readings = [dict(name=r["Room Name"], status=r["Device Status"],
                         stamp=r.Timestamp.strftime("%d %b %Y %H:%M"),
                         temperature=sensor_average(samples, r["Room key"], "Temperature"))
                    for _, r in snapshots.iterrows()] if allowed else []
        output.append({**spec, "sources": list(spec["sources"]), "keys": keys,
            "key": key if row is not None else None, "allowed": allowed,
            "products": products(snapshots), "readings": readings,
            "usage": number(row["Utilisation %"]) if eligible_use else None,
            "rating": number(row.Sentiment) if eligible_rating else None,
            "responses": int(row.Responses) if row is not None else 0,
            "coverage": number(row["Coverage %"]) if row is not None else None,
            "capacity": number(row.Capacity) if row is not None else None,
            "typical": number(row["Typical attendance"]) if row is not None else None,
            "temperature": readings[0]["temperature"] if len(readings) == 1 else None,
            "route": str(row.Route) if row is not None else "Asset" if len(readings) else "No data",
            "plan": pilot_plan(ctx, key) if row is not None else None,
        })
    return output


def choose_space(rows, identity, state):
    """Only an in-scope room may become the room followed through later chapters."""
    chosen = next((r for r in rows if r["id"] == identity and r["allowed"]), None)
    if chosen is None:
        return
    state["office_selected"] = identity
    if chosen["key"]:
        state["selected_room"] = chosen["key"]


@st.cache_data
def picture():
    return "data:image/jpeg;base64," + base64.b64encode((ROOT / "assets/london-office.jpg").read_bytes()).decode()


@st.cache_resource
def _registered_widget(js, css):
    # A content-specific name also invalidates Streamlit's browser-side module.
    version = sha256((js + "\n" + css).encode()).hexdigest()[:12]
    return components.component(f"neat_office_map_{version}", css=css, js=js)


def widget():
    # Changes to a front-end asset must invalidate the registered component.
    return _registered_widget((ROOT / "assets/office-map.js").read_text(),
                              (ROOT / "assets/office-map.css").read_text())


def fit_rows(ctx):
    """Only scoped meeting rooms can drive the seat comparison."""
    from workplace.customer import feedback_in_scope
    return meeting_rows(ctx, feedback_in_scope(ctx))


def meeting_rows(ctx, records):
    """Keep map ratings in the supplied audience/date scope, with no asset scores."""
    portfolio = p.room_portfolio(ctx, records)
    rows = map_rows(ctx, portfolio, st.session_state.get("room_filter", ()))
    return [{**row, "allowed": row["allowed"] and row["key"] is not None}
            for row in rows if row["kind"] == "room"]


def render_fit(ctx, room):
    from html import escape
    from workplace.briefing import heading, html
    rows = fit_rows(ctx)
    selected = next((r["id"] for r in rows if r["key"] == room and r["allowed"]), None)
    heading("Find the room. Test the fit.", "Select a room on the map to update both seat diagrams.")

    def picked():
        event = st.session_state.get("office_fit_map_component", {})
        choose_space(rows, event.get("picked"), st.session_state)

    widget()(data={"image": picture(), "rows": rows, "selected": selected, "view": "fit"},
             key="office_fit_map_component", on_picked_change=picked)
    if selected is None:
        html(f'<div class="brief-small"><b>{escape(room.split(" / ", 1)[-1])}</b> has no confirmed map position. Its seat comparison is shown alongside.</div>')
    html('<div class="brief-small">Confirmed meeting-room positions only. Use the room menu for other rooms. Display areas are excluded from seat comparisons.</div>')


def render_experience(ctx, records, room, audience):
    from html import escape
    from workplace.briefing import heading, html
    rows = meeting_rows(ctx, records)
    selected = next((r["id"] for r in rows if r["key"] == room and r["allowed"]), None)
    heading("How each room feels", "Select a room to try its companion app.")

    def picked():
        event = st.session_state.get("office_experience_map_component", {})
        choose_space(rows, event.get("picked"), st.session_state)

    widget()(data={"image": picture(), "rows": rows, "selected": selected, "view": "experience"},
             key="office_experience_map_component", on_picked_change=picked)
    if selected is None:
        html(f'<div class="brief-small"><b>{escape(room.split(" / ", 1)[-1])}</b> has no confirmed map position. Its companion is ready alongside.</div>')
    html(f'<div class="brief-small">{escape(audience)} · dates and room filters apply. Use the room menu for spaces not positioned on the map.</div>')


def improve_rows(ctx):
    rows = fit_rows(ctx)
    for row in rows:
        focus = row["plan"]["focus"] if row["plan"] else None
        row["action"] = {"Operating schedules": "controls", "Room layout": "layout",
                         "Evidence baseline": "evidence"}.get(focus)
        row["action_label"] = ("Controls + layout" if row["action"] == "controls" and row["route"] == "Controls + layout"
                               else {"controls": "Controls review", "layout": "Layout review", "evidence": "More evidence"}.get(row["action"], "Outside room scope"))
    return rows


def render_improve(ctx, room):
    from html import escape
    from workplace.briefing import heading, html
    rows = improve_rows(ctx)
    selected = next((r["id"] for r in rows if r["key"] == room and r["allowed"]), None)
    heading("Where should we act?", "Select a room to see its next step.")

    def picked():
        event = st.session_state.get("office_improve_map_component", {})
        choose_space(rows, event.get("picked"), st.session_state)

    widget()(data={"image": picture(), "rows": rows, "selected": selected, "view": "improve"},
             key="office_improve_map_component", on_picked_change=picked)
    if selected is None:
        html(f'<div class="brief-small"><b>{escape(room.split(" / ", 1)[-1])}</b> has no confirmed map position. Its recommendation is shown alongside.</div>')
    html('<div class="brief-small">Suggested reviews from the selected observations. Use the room menu for other spaces.</div>')


def render(ctx, portfolio):
    """One compact spatial panel; chart comparison remains in presenter tools."""
    from workplace.briefing import html, heading, preferred_room
    from html import escape
    preferred_room(ctx)
    rows = map_rows(ctx, portfolio, st.session_state.get("room_filter", ()))
    scope_token = sha256(repr((ctx["start"], ctx["end"], ctx["office"],
                              sorted(ctx["inventory"]["Room key"]))).encode()).hexdigest()[:12]
    selected = st.session_state.get("office_selected")
    valid = {r["id"] for r in rows if r["allowed"]}
    if (selected not in valid or st.session_state.get("office_scope") != scope_token
            or st.session_state.get("office_last_room") != st.session_state.get("selected_room")):
        selected = next((r["id"] for r in rows if r["key"] == st.session_state.get("selected_room")), next(iter(sorted(valid)), "A"))
        st.session_state.update(office_selected=selected, office_scope=scope_token)
    st.session_state["office_last_room"] = st.session_state.get("selected_room")
    left, right = st.columns([1.95, 1], gap="medium")
    with left, st.container(key="brief_panel_office"):
        heading("Your office, connected to the evidence", "Select a space · labels show the Neat products reported in the selected period")
        def picked():
            event = st.session_state.get("office_map_component", {})
            choose_space(rows, event.get("picked"), st.session_state)
        widget()(data={"image": picture(), "rows": rows, "selected": selected},
                 key="office_map_component", on_picked_change=picked)
        mapped = {r["key"] for r in rows if r["key"]}
        remaining = portfolio[~portfolio["Room key"].isin(mapped)]
        caption = f'{len(mapped)} of {len(portfolio)} rooms positioned · display areas are separate from room-use totals'
        if len(remaining):
            caption += '. Not yet placed: ' + ', '.join(remaining["Room Name"])
        html(f'<div class="brief-small">{escape(caption)}</div>')
    with right:
        chosen = next(r for r in rows if r["id"] == st.session_state.get("office_selected", selected))
        detail(chosen)
        leaders = []
        for measure, title in [("usage", "Most used"), ("sentiment", "Highest rated · sample")]:
            winners = p.room_leaders(portfolio, measure)
            names = " / ".join(winners["Room Name"]) if len(winners) else "More evidence needed"
            value = (u.fmt(winners.iloc[0]["Utilisation %"], "%", 1) if measure == "usage" else u.fmt(winners.iloc[0].Sentiment, "/5", 2)) if len(winners) else "—"
            leaders.append(f'<div><span>{title}</span><strong>{escape(names)}</strong><b>{escape(value)}</b></div>')
        html('<div class="office-leaders">' + ''.join(leaders) + '</div>')
    with ctx["tools"].expander("Compare room performance"):
        if len(p.comparison_rows(portfolio)):
            st.plotly_chart(p.performance_figure(portfolio, ctx["summary"]["utilisation"], u.FONT),
                            width="stretch", config={"displayModeBar": False}, key="brief_portfolio_plot")
        st.caption("All qualifying rooms remain in this comparison, including rooms whose position has not been supplied. Sample ratings are invented.")
    with ctx["tools"].expander("Office map and equipment"):
        st.caption("Positions confirmed by Ryan. This office illustration is not a measured floor plan. Product counts come from the latest record for each named source within the selected dates, not from furniture in the picture. Status is the last recorded source state, not current sign-in or booking availability.")
        st.caption("The Wall o’ Pads and Shelf o’ Frames share one marker. Their readings remain separate; occupancy and ratings are not combined. The kiosk and lounge asset have no assumed meeting-room capacity.")
        st.caption("Temperature is time-weighted across valid reported sensor intervals within the chosen hours. It is not an HVAC state or a health/safety assessment. The map does not infer air quality from temperature.")
        st.markdown("Product names: [Neat model guide](https://support.neat.no/article/neat-device-attributes-for-microsoft-intune-conditional-access-device-exclusions/). Unidentified codes remain visible without guessing.")


def detail(row):
    from html import escape
    from workplace.briefing import html
    equipment = " · ".join(f'{p["name"]}' + (f' ×{p["count"]}' if p["count"] > 1 else "") for p in row["products"]) or "Equipment not reported in this period"
    markup = f'<article class="office-detail"><div class="brief-label">SELECTED SPACE · {row["id"]}</div><h3>{escape(row["name"])}</h3><p class="office-equipment">{escape(equipment)}</p>'
    if row["kind"] == "room":
        markup += '<div class="office-scores">' + ''.join(f'<div><span>{label}</span><strong>{escape(value)}</strong></div>' for label, value in [
            ("Time in use", u.fmt(row["usage"], "%", 1)), ("Space rating · sample", u.fmt(row["rating"], "/5", 2)),
            ("Mean temperature", u.fmt(row["temperature"], "°C", 1)),
            ("Typical group / seats", f'{u.fmt(row["typical"], digits=1)} / {u.fmt(row["capacity"])}')]) + '</div>'
        markup += f'<p class="office-evidence">{u.fmt(row["coverage"], "%")} occupancy coverage · {row["responses"]} invented responses</p>'
    else:
        markup += '<p class="office-evidence">Display area · no meeting-room usage or satisfaction score assigned.</p>'
    for reading in row["readings"]:
        markup += f'<div class="office-status"><b>{escape(reading["name"])}</b><span>{escape(reading["status"])} · recorded {escape(reading["stamp"])}</span>'
        if row["kind"] != "room":
            markup += f'<span>Mean temperature: {u.fmt(reading["temperature"], "°C", 1)}</span>'
        markup += '</div>'
    if not row["readings"]:
        markup += '<p class="office-evidence">No matching observation in this date and room scope.</p>'
    html(markup + '</article>')
    plan = row["plan"]
    if plan:
        html(f'<article class="brief-recommendation"><div class="brief-label">RECOMMENDED NEXT STEP</div><h3>{escape(plan["title"])}</h3>'
             f'<p>{escape(plan["gate"])}</p><small><b>Owner</b> {escape(plan["owner"])}<br><b>Measure</b> {escape(plan["measure"])}</small></article>')
