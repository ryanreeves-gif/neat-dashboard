import numpy as np
import pandas as pd
import pytest
from workplace import analytics as a
from workplace import visuals as v
from test_analytics import source
from test_app import app


def test_hourly_totals_preserve_gaps_offline_and_partial_hours():
    start, end = pd.Timestamp("2026-09-28 09:50"), pd.Timestamp("2026-09-28 12:05")
    d, _ = a.prepare(source(["2026-09-28 09:50", "2026-09-28 10:00", "2026-09-28 10:10", "2026-09-28 12:00"],
                            [2, 0, 3, 0], **{"Device Status": ["Online", "Online", "Offline", "Online"]}))
    samples = a.intervals(d, start, end, True)
    hourly = v.hourly_occupancy(samples, start, end, True)
    assert hourly.Expected.sum() == pytest.approx(a.window_hours(start, end, True))
    assert hourly.Observed.sum() == pytest.approx(25/60)
    assert hourly.Occupied.sum() == pytest.approx(10/60)
    assert hourly.loc["2026-09-28 09:00", "Utilisation"] == pytest.approx(100)
    assert hourly.loc["2026-09-28 12:00", "Utilisation"] == 0
    assert np.isnan(hourly.loc["2026-09-28 11:00", "Utilisation"])
    assert sum(v.period_balance(hourly)) == pytest.approx(135/60)
    fig = v.occupancy_figure(hourly, capacity=12)
    assert list(fig.data[0].text[0]) == ["16.7%", "?", "?", "0%"]


def test_typical_week_weights_by_observed_hours():
    index = pd.to_datetime(["2026-09-21 09:00", "2026-09-28 09:00"])
    hourly = pd.DataFrame({"Expected": [1, 1], "Observed": [1, .5], "Occupied": [0, .5], "Person hours": [0, 2]}, index=index)
    fig = v.occupancy_figure(hourly, typical=True, capacity=10)
    assert fig.data[0].z[0, 0] == pytest.approx(40/3)
    assert fig.data[0].text[0, 0] == "13.3%*"


def test_average_people_includes_empty_time_but_never_missing_time():
    start, end = pd.Timestamp("2026-09-24 09:00"), pd.Timestamp("2026-09-24 13:00")
    times = list(pd.date_range(start, periods=6, freq="10min"))
    times += list(pd.date_range("2026-09-24 10:00", periods=3, freq="10min"))
    times += list(pd.date_range("2026-09-24 12:00", periods=6, freq="10min"))
    data, _ = a.prepare(source([str(t) for t in times], [6, 6, 6, 0, 0, 0] + [6, 6, 6] + [0]*6))
    hourly = v.hourly_occupancy(a.intervals(data, start, end, False), start, end, False)
    fig = v.occupancy_figure(hourly, capacity=12)
    assert list(fig.data[0].text[0]) == ["25%", "50%*", "?", "0%"]
    assert list(fig.data[0].z[0]) == pytest.approx([25, 50, -1, 0])
    assert fig.layout.meta["capacity"] == 12


def test_capacity_used_matches_people_per_seat_and_needs_known_capacity():
    hourly = pd.DataFrame({"Expected": [1], "Observed": [1], "Occupied": [1], "Person hours": [3.7]},
                          index=pd.to_datetime(["2026-09-24 10:00"]))
    fig = v.occupancy_figure(hourly, capacity=10)
    assert fig.data[0].z[0, 0] == pytest.approx(37)
    assert fig.data[0].text[0, 0] == "37%"
    assert "3.70 / 10 seats" in fig.data[0].customdata[0, 0]
    for unknown in [None, np.nan, 0]:
        assert not v.occupancy_figure(hourly, capacity=unknown).data


def test_sensor_validity_is_independent_of_occupancy_and_excludes_offline():
    start, end = pd.Timestamp("2026-09-28 09:00"), pd.Timestamp("2026-09-28 11:00")
    d, _ = a.prepare(source(pd.date_range(start, periods=4, freq="10min").astype(str), [None]*4,
        Temperature=[20, 22, 90, None], **{"Device Status": ["Online", "Unreported", "Offline", "Online"]}))
    samples = a.intervals(d, start, end, True)
    hourly = v.hourly_sensor(samples, "Temperature", start, end, True)
    assert hourly.iloc[0] == 21
    assert np.isnan(hourly.iloc[1])
    assert v.hourly_occupancy(samples, start, end, True).Observed.sum() == 0


def test_office_hour_grid_excludes_weekend_and_supports_no_observations():
    start, end = pd.Timestamp("2026-09-25 18:30"), pd.Timestamp("2026-09-28 09:15")
    d, _ = a.prepare(source(["2026-09-20 09:00"], [2]))
    samples = a.intervals(d, start, end, True)
    hourly = v.hourly_occupancy(samples, start, end, True)
    assert hourly.Expected.sum() == pytest.approx(1.75)
    assert len(hourly) == 3
    assert hourly.Utilisation.isna().all()
    assert hourly.Coverage.eq(0).all()


def test_environment_cards_and_all_workflow_actions():
    at = app().switch_page("pages/Environment.py").run()
    assert not at.exception
    for signal in ["Light Level", "Humidity", "VOC", "Temperature"]:
        at.button(key=f"sensor_select_{signal}").click().run()
        assert not at.exception
        assert at.session_state["environment_signal"] == signal
    for action in ["eco", "temperature", "lights", "purge"]:
        at.selectbox(key="environment_action").select(action).run()
        at.button(key="environment_run").click().run()
        assert not at.exception
        result = at.session_state["environment_demo_run"]["payload"]
        assert result["action"] == action
        assert len(result["events"]) == 6
        assert result["command_sent"] is False
        assert result["service_now_ticket_id"] is None
        assert result["measured_outcome"] is None
        assert result["mode"] == "simulation"
        if action == "purge":
            assert result["basis"] == "manual_scenario"
        technical = next(e for e in at.expander if e.label == "Technical sequence of events")
        assert technical.proto.expanded is False
    at.slider(key="environment_duration").set_value(30).run()
    assert not at.exception
    assert not any(e.label == "Technical sequence of events" for e in at.expander)


def test_pattern_modes_long_window_and_room_findings_expand():
    at = app().switch_page("pages/Spaces.py").run()
    assert not at.exception
    at.radio(key="room_history_mode").set_value("Typical week").run()
    at.selectbox(key="_preset").select("Last 90 days").run()
    assert not at.exception
    at.radio(key="room_history_mode").set_value("By date").run()
    assert at.selectbox(key="room_history_window")
    assert not at.exception
    at.selectbox(key="room_signal").select("Temperature").run()
    assert not at.exception
    assert any(e.label == "Details and next step" and not e.proto.expanded for e in at.expander)
