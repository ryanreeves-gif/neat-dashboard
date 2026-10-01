from hashlib import sha256
import pandas as pd
import pytest

from workplace import conclusions as x
from test_app import app
from test_executive import context_fixture


def test_room_type_comparison_pools_hours_and_excludes_insufficient_evidence():
    ctx = context_fixture()
    # A short, always-busy room must not outweigh a long, lightly used room.
    ctx["stats"].loc[:, "Capacity"] = [6, 6, 12]
    ctx["stats"].loc[:, "Observed hours"] = [2, 10, 10]
    ctx["stats"].loc[:, "Occupied hours"] = [2, 0, 1]
    ctx["stats"].loc[:, "Coverage %"] = [100, 100, 69]
    ranked = x.room_type_ranking(ctx)
    assert len(ranked) == 1 and ranked.iloc[0].Rooms == 2
    assert ranked.iloc[0]["Time in use %"] == pytest.approx(100 * 2 / 12)
    ctx["stats"].loc[:, "Coverage %"] = 0
    assert x.room_type_ranking(ctx).empty
    assert x.improvement_summary(ctx)["rooms"] == 0
    ctx["summary"]["coverage"] = 0
    assert "Strengthen the evidence" in x.conclusion(ctx, x.improvement_summary(ctx))[0]


def test_ties_and_zero_use_never_become_a_false_unique_winner():
    ranking = pd.DataFrame({"Time in use %": [25.01, 25.04, 20], "Room type": ["A", "B", "C"]})
    assert x.leaders(ranking)["Room type"].tolist() == ["A", "B"]
    ranking["Time in use %"] = 0
    assert x.leaders(ranking).empty
    assert x.room_type(0) is None and x.room_type(float("nan")) is None


def test_device_highlight_keeps_unknown_models_and_the_actual_leading_room():
    ctx = context_fixture()
    ctx["inventory"]["Neat Equipment"] = [" nf23k1+NF23K1 + nf25j1 + UNSURE", "NF22E1", "NF21F1"]
    lead = x.leading_room(ctx)
    assert lead["Room Name"] == "Arran"
    assert lead["equipment"] == {"video": ["Neat Board Pro"], "other": ["Neat Pad Pro"], "unmapped": ["UNSURE"]}
    ctx["inventory"].loc[ctx["inventory"]["Room Name"].eq("Arran"), "Neat Equipment"] = None
    # Missing metadata must not silently promote another room's device.
    assert x.leading_room(ctx)["Room Name"] == "Arran"
    assert x.leading_room(ctx)["equipment"]["video"] == []
    ctx["stats"]["Occupied hours"] = 0
    assert x.leading_room(ctx) is None


def test_planning_cases_respect_scope_currency_unknown_zero_and_examples():
    rooms = ["London EC / Arran", "Oslo EC / Fjell"]
    state = {}
    for room, currency, values in [(rooms[0], "GBP", [18000, 9000, 1500]),
                                   (rooms[0], "EUR", [1000, 0, 100]),
                                   (rooms[1], "GBP", [0, 0, 0])]:
        token = sha256(room.encode()).hexdigest()[:12] + "_" + currency
        state.update({f"value_{token}_{k}": v for k, v in zip(["project", "savings", "extra"], values)})
        state[f"value_{token}_example"] = currency == "GBP"
    cases = x.planning_cases(state, [rooms[0]])
    assert len(cases) == 2  # currencies stay separate; Oslo stays out of scope
    assert [r["annual_net"] for r in cases] == [7500, -100]
    assert [r["example"] for r in cases] == [True, False]
    assert x.planning_cases(state, [rooms[1]])[0]["annual_net"] == 0
    state.pop(f"value_{sha256(rooms[0].encode()).hexdigest()[:12]}_GBP_savings")
    assert len(x.planning_cases(state, [rooms[0]])) == 1


def test_overview_illustration_is_opt_in_and_saved_case_returns_from_value_page():
    at = app()
    assert not at.exception
    assert at.toggle(key="_overview_example").value is False
    at.toggle(key="_overview_example").set_value(True).run()
    assert not at.exception
    assert any("7,500" in e.value for e in at.markdown)
    at.switch_page("pages/Value.py").run()
    at.button(key="value_example").click().run()
    room = at.selectbox(key="_selected_room").value
    at.switch_page("app.py").run()
    assert not at.exception
    assert any(room in e.value for e in at.caption)
    at.button(key="overview_edit_case").click().run()
    at.switch_page("pages/Value.py").run()
    assert not at.exception
    assert at.selectbox(key="_selected_room").value == room
    assert at.selectbox(key="_value_currency").value == "GBP"
    at.switch_page("app.py").run()
    # A case belonging to another room must disappear when the shared scope changes.
    other = next(r for r in at.multiselect(key="_room_filter").options if r != room)
    at.session_state["overview_example"] = False
    at.multiselect(key="_room_filter").set_value([other]).run()
    assert not at.exception
    assert any("not been costed" in e.value for e in at.markdown)
    assert not any("7,500" in e.value for e in at.markdown)
