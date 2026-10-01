from hashlib import sha256

import pandas as pd
import pytest

from workplace import analytics as a
from workplace.scenarios import attendance_bands, evaluate_layout, export_comparison, room_evidence
from test_analytics import source
from test_app import app


def evidence_fixture():
    # 20 min with two people, 10 min with six, 10 min empty, 10 min offline,
    # then a long unknown gap. A second room must never enter this model.
    raw = source(pd.date_range("2026-09-28 09:00", periods=5, freq="10min").astype(str), [2, 2, 6, 0, 50],
                 **{"Device Status": ["Online"]*4 + ["Offline"]})
    other = source(["2026-09-28 09:00"], [100], **{"Room Name": ["B"]})
    data, _ = a.prepare(pd.concat([raw, other], ignore_index=True))
    samples = a.intervals(data, pd.Timestamp("2026-09-28 09:00"), pd.Timestamp("2026-09-28 11:00"), True)
    return room_evidence(samples, "London / A", 2)


def test_two_rooms_do_not_combine_to_fit_one_group_and_gaps_do_not_become_demand():
    evidence = evidence_fixture()
    two_small = evaluate_layout(evidence, [4, 4])
    one_large = evaluate_layout(evidence, [8])
    assert two_small["total_seats"] == one_large["total_seats"] == 8
    assert two_small["fit_percent"] == pytest.approx(200/3)
    assert one_large["fit_percent"] == 100
    assert two_small["exceeds_hours"] == pytest.approx(1/6)
    assert evidence["coverage"] == pytest.approx(100/3)
    assert evidence["peak"] == 6
    assert evidence["unknown_hours"] == pytest.approx(4/3)
    assert evidence["empty_hours"] == pytest.approx(1/6)
    assert attendance_bands(evidence).percent.sum() == pytest.approx(100)


def test_no_occupied_time_is_unknown_not_perfect_fit_and_cost_zero_is_explicit():
    evidence = evidence_fixture()
    evidence.update(occupied=evidence["occupied"].iloc[:0], occupied_hours=0)
    result = evaluate_layout(evidence, [4, 6])
    assert result["fit_percent"] is None
    assert result["exceeds_hours"] is None
    assert result["project_cost"] is None
    assert evaluate_layout(evidence, [4], 0)["project_cost"] == 0
    for seats in [[], [0], [-1], [3.5], [float("nan")], [4, 4, 4]]:
        with pytest.raises(ValueError):
            evaluate_layout(evidence, seats)
    with pytest.raises(ValueError):
        evaluate_layout(evidence, [4], -100)


def test_export_carries_evidence_scope_assumptions_and_unknown_cost():
    evidence = evidence_fixture()
    ctx = dict(start=pd.Timestamp("2026-09-28 09:00"), end=pd.Timestamp("2026-09-28 11:00"), office=True, demo=True)
    export = export_comparison(ctx, "London / A", evidence, [("Option A", evaluate_layout(evidence, [4, 4]))], "GBP")
    row = export.iloc[0]
    assert row["Room"] == "London / A"
    assert row["Entered project cost"] is None
    assert row["Source"] == "Generated demonstration data"
    assert row["Fit % of occupied time"] == pytest.approx(200/3)
    assert "do not split" in row["Assumptions"]
    assert "payback" in row["Assumptions"]


def test_scenario_navigation_editing_and_room_state_survive_filters():
    at = app().switch_page("pages/Spaces.py").run()
    room = at.selectbox(key="_selected_room").value
    at.button(key="room_scenarios").click().run()
    at.switch_page("pages/Scenarios.py").run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.selectbox(key="_selected_room").value == room
    token = sha256(room.encode()).hexdigest()[:12]
    key = f"_scenario_{token}_a_first"
    cost = f"_scenario_{token}_a_cost_GBP"
    at.number_input(key=key).set_value(3).run()
    at.number_input(key=cost).set_value(12000.0).run()
    at.checkbox(key=f"_scenario_{token}_a_split").check().run()
    assert not at.exception
    at.selectbox(key="_preset").select("Last 30 days").run()
    assert at.number_input(key=key).value == 3
    assert at.number_input(key=cost).value == 12000
    rooms = at.selectbox(key="_selected_room").options
    other = next(r for r in rooms if r != room)
    at.selectbox(key="_selected_room").select(other).run()
    assert not at.exception
    at.selectbox(key="_selected_room").select(room).run()
    assert at.number_input(key=key).value == 3
    assert at.number_input(key=cost).value == 12000
    at.selectbox(key="_scenario_currency").select("EUR").run()
    assert at.number_input(key=f"_scenario_{token}_a_cost_EUR").value is None
    assert not at.exception
