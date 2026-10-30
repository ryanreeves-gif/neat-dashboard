from hashlib import sha256

import pandas as pd

from workplace.decision import closing_evidence
from test_executive import context_fixture
from test_briefing import presentation


def records():
    return pd.DataFrame([
        dict(room_key="London EC / Arran", audience=group, experience=score, equipment=score)
        for group, score in [("Neat employee", 3), ("Customer / guest", 5)] for _ in range(6)
    ])


def test_closing_uses_observed_fit_and_keeps_audiences_and_money_separate():
    ctx = context_fixture()
    room = "London EC / Arran"
    key = sha256(room.encode()).hexdigest()[:12]
    case = dict(room=room, example=False, annual_net=1200, currency="GBP")
    model = closing_evidence(ctx, records(), room, {"brief_seats_" + key: 3}, case)
    assert model["demand"]["value"] == "100.0%"
    assert model["opportunity"]["value"] == "12 → 3"
    assert "100.0% of observed occupied time fits" in model["opportunity"]["detail"]
    assert [r["value"] for r in model["cohorts"]] == ["0.0%", "100.0%"]
    assert model["case"] is case
    assert closing_evidence(ctx, records(), room, {}, {**case, "example": True})["case"] is None
    assert closing_evidence(ctx, records(), room, {}, {**case, "room": "London EC / Barra"})["case"] is None
    employee = closing_evidence(ctx, records(), room, {"feedback_audience": "Neat employee"})
    assert [r["name"] for r in employee["cohorts"]] == ["Employees"]
    small = closing_evidence(ctx, records().head(4), room, {})
    assert all(r["value"] == "—" for r in small["cohorts"])


def test_closing_respects_review_route_and_cannot_promote_limited_evidence():
    ctx = context_fixture()
    room = "London EC / Barra"
    state = {"brief_control_room": room, "brief_condition": "purge"}
    model = closing_evidence(ctx, records(), room, state)
    assert model["plan"]["focus"] == "Operating schedules"
    assert "Warm while recorded empty" in model["opportunity"]["detail"]
    assert "not proof of wasted energy" in model["opportunity"]["source"]
    ctx["stats"]["Coverage %"] = 60
    model = closing_evidence(ctx, records(), room, state)
    assert model["demand"]["value"] == "—"
    assert model["plan"]["focus"] == "Evidence baseline"
    assert model["opportunity"]["value"] == "60%"
    assert "No qualifying intervention" in model["opportunity"]["detail"]


def test_closing_page_has_no_new_main_controls_and_follows_the_improve_proposal():
    at = presentation().switch_page("pages/Environment.py").run()
    assert not at.exception, [e.message for e in at.exception]
    room = at.session_state["selected_room"]
    at.main.get("button_group")[0].set_value("Room layout").run()
    next(n for n in at.number_input if n.label == "Proposed room seats").set_value(3).run()
    at.toggle(key="_overview_example").set_value(True).run()
    at.switch_page("pages/Next_Steps.py").run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.session_state["selected_room"] == room
    assert not at.main.button and not at.main.get("button_group") and not at.get("iframe")
    assert len(at.main.selectbox) == 2  # dates and office hours; no extra menus
    markup = " ".join(e.proto.body for e in at.get("html"))
    for text in ["01 · PROTECT WHAT WORKS", "02 · LISTEN TO PEOPLE", "03 · TEST ONE IMPROVEMENT",
                 "→ 3", "Validate demand. Trial a reversible layout.", "SUCCESS MEASURE", "05 / 05"]:
        assert text in markup
    assert "£7,500" not in markup
    at.main.multiselect(key="_room_filter").set_value([room]).run()
    assert not at.exception and at.main.multiselect(key="_room_filter").value == [room]
    at.toggle(key="_presentation_mode").set_value(False).run()
    assert not at.exception, [e.message for e in at.exception]
