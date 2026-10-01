from io import BytesIO
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from workplace import analytics as a
from workplace.brief import pdf_brief
from workplace.executive import decision_actions, evidence_summary


def context_fixture():
    rows = []
    for room, people, temp, light in [("Arran", 3, 21, 20), ("Barra", 0, 24, 20), ("Harris", 0, 20, 200)]:
        for stamp in pd.date_range("2026-09-28 08:00", "2026-09-28 19:00", freq="10min"):
            rows.append({"Timestamp": str(stamp), "Location": "London EC", "Room Name": room,
                         "Device Status": "Online", "Occupancy": people, "Capacity": 12,
                         "Temperature": temp, "Light Level": light})
    data, quality = a.prepare(pd.DataFrame(rows))
    start, end = pd.Timestamp("2026-09-28 08:00"), pd.Timestamp("2026-09-28 19:00")
    samples = a.intervals(data, start, end, True)
    inv = a.inventory(data)
    stats = a.room_statistics(samples, inv, 11)
    return dict(samples=samples, inventory=inv, stats=stats, summary=a.summarise(samples, 11, 3),
                issues=a.findings(samples, stats), start=start, end=end, office=True,
                latest_source=data.Timestamp.max(), quality=quality, demo=False)


def test_low_room_coverage_cannot_be_hidden_by_estate_average():
    ctx = context_fixture()
    ctx["stats"].loc[ctx["stats"]["Room Name"] == "Arran", "Coverage %"] = 69.9
    actions = decision_actions(ctx)
    assert actions[0]["kind"] == "coverage"
    assert all(action["room_key"] != "London EC / Arran" for action in actions)
    assert evidence_summary(ctx)["rooms_ready"] == 2
    assert ctx["issues"]["Room key"].eq("London EC / Arran").any()  # detail remains available


def test_decisions_retain_scope_and_never_invent_costs_or_savings():
    ctx = context_fixture()
    ctx["issues"] = ctx["issues"].query("Room == 'Arran'")
    actions = decision_actions(ctx)
    assert len(actions) == 1
    assert actions[0]["scope"] == "London EC / Arran"
    assert actions[0]["cost"] == "Not assessed"
    assert "bookings" in actions[0]["action"]
    ctx["issues"] = ctx["issues"].iloc[:0]
    assert decision_actions(ctx)[0]["kind"] == "baseline"


def test_one_page_pdf_has_evidence_actions_and_limitations():
    ctx = context_fixture()
    reader = PdfReader(BytesIO(pdf_brief(ctx)))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    for phrase in ["London EC", "28 Sep 2026", "100%", "Arran", "Barra", "Harris",
                   "Cost: Not assessed", "TIME IN USE", "Before approving an investment",
                   "Costs and savings have not been assessed"]:
        assert phrase in text
    assert "Generated sample data" not in text


def test_pdf_marks_demonstration_and_zero_evidence_explicitly():
    ctx = context_fixture()
    ctx["demo"] = True
    ctx["stats"]["Coverage %"] = 0
    ctx["summary"].update(coverage=0, valid_hours=0, utilisation=float("nan"), attendance=float("nan"))
    text = PdfReader(BytesIO(pdf_brief(ctx))).pages[0].extract_text()
    assert "Demonstration data" in text
    assert "Generated sample data; not customer evidence" in text
    assert "Unknown" in text
    assert "Strengthen the evidence" in text


def test_pdf_handles_long_and_escaped_room_names():
    ctx = context_fixture()
    ctx["issues"].loc[0, "Evidence"] = "<Observed> & reviewed: 90% of occupied time had <=3 people / 12 seats"
    name = "London EC / " + "Long meeting-room name " * 6
    old = ctx["issues"].loc[0, "Room key"]
    ctx["issues"].loc[0, "Room key"] = name
    ctx["stats"].loc[ctx["stats"]["Room key"] == old, "Room key"] = name
    reader = PdfReader(BytesIO(pdf_brief(ctx)))
    assert len(reader.pages) == 1
    assert "<Observed> & reviewed" in reader.pages[0].extract_text()


def test_app_export_follows_room_filter(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from workplace import views

    exports = []

    def capture(ctx):
        blob = pdf_brief(ctx)
        exports.append((set(ctx["inventory"]["Room key"]), ctx["summary"]["rooms"], blob))
        return blob

    monkeypatch.setattr(views, "pdf_brief", capture)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=45)
    app.session_state["demo_mode"] = True
    app.session_state["presentation_mode"] = False
    app.run()
    assert not app.exception
    options = app.multiselect(key="_room_filter").options
    app.multiselect(key="_room_filter").set_value([options[1]]).run()
    assert not app.exception
    rooms, count, blob = exports[-1]
    assert rooms == {options[1]}
    assert count == 1
    reader = PdfReader(BytesIO(blob))
    assert len(reader.pages) == 1
    assert "1 monitored rooms" in reader.pages[0].extract_text()
