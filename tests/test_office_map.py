from copy import deepcopy
from pathlib import Path
import json

import pandas as pd
from streamlit.testing.v1 import AppTest

from workplace import analytics as a, portfolio as p
from workplace.office_map import applies, choose_space, map_rows, meeting_rows, products
from workplace.feedback import sample_feedback


def office_fixture():
    raw = []
    for name, seats, kit in [
        ("Arran", 12, "NF23K1 + NF23K1 + NF25J1"),
        ("Barra", 7, "NF22H1 + NF25A5"),
        ("Wall o' Pads", 0, "NF25A5 + NF25A5"),
        ("Shelf o' Frames", 0, "NF21F1 + NF21F1 + NF21F1"),
        ("Longrow Lounge Board 32", None, "NF25M1"),
        ("London Envoy Kiosk", 0, "NF21F1"),
        ("Z Longrow Zoom", None, "NF21D1"),
    ]:
        for t in pd.date_range("2026-10-26 08:00", "2026-10-26 19:00", freq="10min"):
            raw.append(dict(Timestamp=t.isoformat(), Location="London EC", **{"Room Name": name,
                "Capacity": seats, "Neat Equipment": kit, "Device Status": "Online",
                "Occupancy": 3, "Temperature": 23 if name == "Wall o' Pads" else 21}))
    data, quality = a.prepare(pd.DataFrame(raw))
    start, end = pd.Timestamp("2026-10-26 08:00"), pd.Timestamp("2026-10-26 19:00")
    inv = a.inventory(data); inv = inv[inv.Capacity.gt(0)]
    samples = a.intervals(data[data["Room key"].isin(inv["Room key"])], start, end, True)
    stats = a.room_statistics(samples, inv, 11)
    ctx = dict(data=data, all_data=data, inventory=inv, samples=samples, stats=stats,
               summary=a.summarise(samples, 11, len(inv)), issues=a.findings(samples, stats),
               start=start, end=end, office=True, demo=False)
    feedback = sample_feedback(data)
    return ctx, p.room_portfolio(ctx, feedback)


def test_map_uses_confirmed_names_and_preserves_shared_asset_identity():
    ctx, portfolio = office_fixture()
    rows = {r["id"]: r for r in map_rows(ctx, portfolio)}
    assert rows["G"]["key"] == "London EC / Arran"
    assert rows["A"]["key"] == "London EC / Barra"
    assert rows["F"]["readings"] == []  # retired Zoom alias cannot fill Longrow
    assert rows["E"]["products"][0]["name"] == "Neat Board 32"
    assert rows["H"]["usage"] is None and rows["H"]["rating"] is None
    assert rows["H"]["temperature"] is None  # two sensors never become one made-up average
    assert {round(r["temperature"], 6) for r in rows["H"]["readings"]} == {21, 23}
    assert {(p["name"], p["count"]) for p in rows["H"]["products"]} == {("Neat Pad Gen 2", 2), ("Neat Frame", 3)}
    assert ctx["summary"]["rooms"] == 2  # display assets do not change the meeting-room total


def test_filtered_missing_and_offline_values_never_become_good_scores():
    ctx, portfolio = office_fixture()
    rows = {r["id"]: r for r in map_rows(ctx, portfolio, ["London EC / Arran"])}
    assert rows["A"]["allowed"] is False and rows["A"]["usage"] is None
    assert rows["G"]["usage"] == 100
    ctx["samples"].loc[:, "Device Status"] = "Offline"
    portfolio.loc[portfolio["Room key"].eq("London EC / Arran"), "Usage eligible"] = False
    rows = {r["id"]: r for r in map_rows(ctx, portfolio)}
    assert rows["G"]["temperature"] is None and rows["G"]["usage"] is None
    ctx["start"] = pd.Timestamp("2026-10-27")
    ctx["end"] = pd.Timestamp("2026-10-28")
    rows = {r["id"]: r for r in map_rows(ctx, portfolio)}
    assert rows["H"]["products"] == [] and rows["H"]["readings"] == []


def test_selection_follows_eligible_rooms_and_assets_do_not_replace_them():
    ctx, portfolio = office_fixture()
    rows = map_rows(ctx, portfolio)
    state = {}
    choose_space(rows, "G", state)
    assert state["selected_room"] == "London EC / Arran"
    choose_space(rows, "H", state)
    assert state["office_selected"] == "H" and state["selected_room"] == "London EC / Arran"
    choose_space(rows, "bad-id", state)
    assert state["office_selected"] == "H"
    assert applies(ctx)
    other = deepcopy(ctx); other["demo"] = True
    assert not applies(other)
    other["demo"] = False; other["inventory"].loc[:, "Location"] = "Oslo EC"
    assert not applies(other)


def test_equipment_counts_unknown_codes_and_markup_are_not_guessed():
    result = products(pd.DataFrame([{"Neat Equipment": "NF21F1 + NF21F1 + XX999"}]))
    assert {r["name"]: r["count"] for r in result} == {"Neat Frame": 2, "Unidentified model XX999": 1}


def test_sentiment_map_respects_audience_and_minimum_response_count():
    ctx, _ = office_fixture()
    records = pd.DataFrame([
        dict(room_key="London EC / Arran", audience=audience, experience=score, equipment=score)
        for audience, score in [("Neat employee", 3), ("Customer / guest", 5)] for _ in range(6)
    ])
    for audience, score in [("Neat employee", 3), ("Customer / guest", 5)]:
        rows = {r["id"]: r for r in meeting_rows(ctx, records[records.audience.eq(audience)])}
        assert rows["G"]["rating"] == score and rows["G"]["responses"] == 6
        assert rows["A"]["rating"] is None and rows["A"]["responses"] == 0
        assert all(r["kind"] == "room" for r in rows.values())
    limited = {r["id"]: r for r in meeting_rows(ctx, records.head(4))}
    assert limited["G"]["rating"] is None and limited["G"]["responses"] == 4


def test_london_map_renders_with_scoped_source_and_keeps_other_chapters(monkeypatch):
    from workplace import data as source
    ctx, portfolio = office_fixture()
    monkeypatch.setattr(source, "observations", lambda *args: (ctx["data"], {"rows":len(ctx["data"]), "invalid_dates":0,
                        "duplicates":0, "date_order":"iso", "status_unreported":False}, pd.Timestamp("2026-10-26 19:00")))
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=60).run()
    assert not at.exception, [e.message for e in at.exception]
    rendered = " ".join(e.proto.body for e in at.get("html"))
    assert "Your office, connected to the evidence" in rendered
    assert "Neat Board Pro ×2" in rendered
    at.multiselect(key="_room_filter").set_value(["London EC / Barra"]).run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.session_state["office_selected"] == "A"
    at.switch_page("pages/Spaces.py").run()
    assert not at.exception
    assert at.selectbox(key="_selected_room").value == "London EC / Barra"
    rendered = " ".join(e.proto.body for e in at.get("html"))
    assert "Find the room. Test the fit." in rendered
    assert "Current room · 7 seats" in rendered
    assert "Smaller-room option · 3 seats" in rendered
    assert "Purple people show the average group while occupied" in rendered
    assert len(at.get("image")) == 2
    payload = json.loads(at.get("bidi_component")[0].proto.json)
    assert payload["view"] == "fit" and payload["selected"] == "A"
    assert all(row["kind"] == "room" for row in payload["rows"])
    assert {row["id"] for row in payload["rows"] if row["allowed"]} == {"A"}
    at.multiselect(key="_room_filter").set_value([]).run()
    at.selectbox(key="_selected_room").select("London EC / Arran").run()
    assert not at.exception, [e.message for e in at.exception]
    payload = json.loads(at.get("bidi_component")[0].proto.json)
    assert payload["selected"] == "G"
    rendered = " ".join(e.proto.body for e in at.get("html"))
    assert "Current room · 12 seats" in rendered
    assert "Smaller-room option · 6 seats" in rendered
    at.switch_page("pages/Feedback.py").run()
    assert not at.exception, [e.message for e in at.exception]
    payload = json.loads(at.get("bidi_component")[0].proto.json)
    assert payload["view"] == "experience" and payload["selected"] == "G"
    assert any(b.label == "Share feedback" for b in at.button)
    rendered = " ".join(e.proto.body for e in at.get("html"))
    assert "Sentiment overview" in rendered and "How each room feels" in rendered
    assert "Arran · London EC" in rendered
    summary = next(e.proto.body for e in at.get("html") if 'brief-metrics stacked' in e.proto.body)
    at.selectbox(key="_selected_room").select("London EC / Barra").run()
    assert not at.exception, [e.message for e in at.exception]
    payload = json.loads(at.get("bidi_component")[0].proto.json)
    assert payload["selected"] == "A"
    assert any("Barra · London EC" in e.proto.body for e in at.get("html"))
    assert next(e.proto.body for e in at.get("html") if 'brief-metrics stacked' in e.proto.body) == summary
    total = sum(r["responses"] for r in payload["rows"])
    at.selectbox(key="_feedback_audience").select("Customer / guest").run()
    assert not at.exception, [e.message for e in at.exception]
    payload = json.loads(at.get("bidi_component")[0].proto.json)
    assert sum(r["responses"] for r in payload["rows"]) < total
    assert payload["selected"] == "A"

    at.selectbox(key="_preset").select("Custom dates").run()
    day = pd.Timestamp("2026-10-26").date()
    at.date_input(key="_custom_dates").set_value((day, day)).run()
    at.switch_page("pages/Environment.py").run()
    assert not at.exception, [e.message for e in at.exception]
    payload = json.loads(at.get("bidi_component")[0].proto.json)
    assert payload["view"] == "improve" and payload["selected"] == "A"
    assert all(r["action"] == "layout" for r in payload["rows"] if r["allowed"])
    assert len(at.get("image")) == 2 and not at.main.button
    at.selectbox(key="_selected_room").select("London EC / Arran").run()
    assert not at.exception, [e.message for e in at.exception]
    payload = json.loads(at.get("bidi_component")[0].proto.json)
    assert payload["selected"] == "G"
    assert any("Current room · 12 seats" in e.proto.body for e in at.get("html"))
    at.multiselect(key="_room_filter").set_value(["London EC / Arran"]).run()
    assert not at.exception
    payload = json.loads(at.get("bidi_component")[0].proto.json)
    assert {r["id"] for r in payload["rows"] if r["allowed"]} == {"G"}
