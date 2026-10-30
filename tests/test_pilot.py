from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from workplace.pilot import pilot_options, pilot_plan, scoped_case
from test_executive import context_fixture


def test_proposals_require_coverage_and_never_invent_an_intervention():
    ctx = context_fixture()
    room = "London EC / Arran"
    assert pilot_options(ctx, room) == ["Room layout"]
    assert pilot_plan(ctx, room)["owner"] == "Workplace + IT / AV"
    ctx["stats"].loc[ctx["stats"]["Room key"].eq(room), "Coverage %"] = 69.9
    assert pilot_options(ctx, room) == ["Evidence baseline"]
    assert pilot_plan(ctx, room, "Room layout")["focus"] == "Evidence baseline"
    ctx["stats"].loc[ctx["stats"]["Room key"].eq(room), "Coverage %"] = float("nan")
    assert pilot_options(ctx, room) == ["Evidence baseline"]


def test_controls_and_no_signal_proposals_have_distinct_owners():
    ctx = context_fixture()
    assert pilot_plan(ctx, "London EC / Barra")["owner"] == "Facilities + IT / BMS"
    ctx["issues"] = ctx["issues"].iloc[:0]
    assert pilot_options(ctx, "London EC / Barra") == ["Evidence baseline"]


def test_finance_cannot_leak_from_another_room_or_an_illustration():
    case = {"room": "London EC / Arran", "example": False, "annual_net": 1200}
    assert scoped_case(case, case["room"]) is case
    assert scoped_case(case, "London EC / Barra") is None
    assert scoped_case({**case, "example": True}, case["room"]) is None
    assert scoped_case(None, case["room"]) is None


def test_held_observations_do_not_refetch_until_release_or_source_change(monkeypatch):
    from workplace import data
    state = {"hold_observations": True}
    calls = []
    monkeypatch.setattr(data.st, "session_state", state)

    def fetch(source, order, demo):
        calls.append((source, order, demo))
        return pd.DataFrame({"value": [len(calls)]}), {}, pd.Timestamp("2026-10-30")

    monkeypatch.setattr(data, "fetch", fetch)
    first = data.observations("source-a", "iso", False)
    assert data.observations("source-a", "iso", False) is first
    assert len(calls) == 1
    data.observations("source-a", "iso", True)
    data.observations("source-b", "iso", True)
    data.observations("source-b", "dayfirst", True)
    assert len(calls) == 4
    state.pop("held_observations")  # explicit refresh
    data.observations("source-b", "dayfirst", True)
    assert len(calls) == 5
    state["hold_observations"] = False
    data.observations("source-b", "dayfirst", True)
    assert "held_observations" not in state
    assert len(calls) == 6


def test_customer_pilot_keeps_scope_and_does_not_fabricate_after_results():
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=60)
    at.session_state["demo_mode"] = True
    at.run()
    at.toggle(key="_hold_observations").set_value(True).run()
    at.switch_page("pages/Improve.py").run()
    assert not at.exception, [e.message for e in at.exception]
    html = " ".join(e.proto.body for e in at.get("html"))
    for phrase in ["Three practical next steps", "Measure", "Owner", "Held snapshot"]:
        assert phrase in html
    assert any("No measured pilot outcome" in caption.value for caption in at.caption)
    assert any("Financial return is still to quantify for this room" in item.value for item in at.markdown)
    assert len(at.main.button) == 1
    assert at.main.button[0].key == "brief_run"
    assert not at.main.get("button_group")
    room = at.selectbox(key="_selected_room").value
    at.multiselect(key="_room_filter").set_value([room]).run()
    assert not at.exception
    assert at.selectbox(key="_selected_room").options == [room]
    at.switch_page("pages/Spaces.py").run()
    assert not at.exception
    assert at.selectbox(key="_selected_room").value == room
    assert at.toggle(key="_hold_observations").value is True
