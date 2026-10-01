import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from workplace import analytics as a
from workplace.feedback import AUDIENCES, demo_record, feedback_summary, filter_feedback, sample_feedback
from workplace.peers import compare_peer
from test_analytics import source
from test_app import app


def dated_rooms():
    dates = pd.date_range("2026-04-09 08:00", "2026-10-01 18:00", freq="h")
    dates = dates[(dates.dayofweek < 5) & (dates.hour >= 8) & (dates.hour < 19)]
    # Remove a whole date; samples must not bridge it.
    dates = dates[dates.normalize() != pd.Timestamp("2026-06-10")]
    raw = source(dates.astype(str), [2] * len(dates), **{"Capacity": [12] * len(dates)})
    return a.prepare(raw)[0]


def test_sample_history_is_stable_date_aligned_positive_and_always_labelled():
    data = dated_rooms()
    result = sample_feedback(data)
    assert result.timestamp.min().date() == data.Timestamp.min().date()
    assert result.timestamp.max().date() == data.Timestamp.max().date()
    assert set(result.timestamp).issubset(set(data.Timestamp))
    assert not result.timestamp.dt.normalize().eq(pd.Timestamp("2026-06-10")).any()
    assert result.is_demo.all() and result.response_id.is_unique
    assert result.source.eq("Generated sample").all()
    prefix = sample_feedback(data[data.Timestamp.lt("2026-08-01")])
    pd.testing.assert_frame_equal(prefix, result[result.timestamp.lt("2026-08-01")].reset_index(drop=True))
    scores = result.groupby("audience").experience.mean()
    assert scores[AUDIENCES[1]] > 4.7 > scores[AUDIENCES[0]] > 4
    # Invented opinions must not be driven by room telemetry.
    changed = data.assign(Occupancy=99, Temperature=35)
    pd.testing.assert_frame_equal(result, sample_feedback(changed))


def test_scope_and_empty_feedback_do_not_invent_scores():
    records = sample_feedback(dated_rooms())
    start, end = pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-02 12:00")
    guests = filter_feedback(records, ["London / A"], start, end, True, AUDIENCES[1])
    assert len(guests) and guests.audience.eq(AUDIENCES[1]).all()
    assert guests.timestamp.between(start, end).all()
    assert filter_feedback(records, ["Nonexistent room"], start, end).empty
    assert feedback_summary(guests.iloc[:0])["positive"] is None
    empty = sample_feedback(dated_rooms().assign(Capacity=0))
    assert filter_feedback(empty, [], start, end).empty
    room = dated_rooms().iloc[0]
    with pytest.raises(ValueError):
        demo_record(room, "Unknown", 5, 5, timestamp=start, response_id="x", source="demo", clock="UTC")
    with pytest.raises(ValueError):
        demo_record(room, AUDIENCES[0], 0, 5, timestamp=start, response_id="x", source="demo", clock="UTC")


def test_peer_uses_capacity_then_location_and_never_matches_itself_or_stale_room():
    chunks = []
    for name, location, seats, dates in [
        ("Arran", "London EC", 12, ["2026-09-28 09:00", "2026-09-28 09:10"]),
        ("Smaller", "London EC", 10, ["2026-09-28 09:00", "2026-09-28 09:10"]),
        ("Fjell", "Oslo EC", 12, ["2026-09-28 09:00", "2026-09-28 09:10"]),
        ("Retired", "London EC", 12, ["2026-06-01 09:00"]),
        ("Too small", "London EC", 4, ["2026-09-28 09:00"])]:
        chunks.append(source(dates, [2]*len(dates), **{"Room Name": [name]*len(dates), "Location": [location]*len(dates), "Capacity": [seats]*len(dates)}))
    data = a.prepare(pd.concat(chunks))[0]
    start, end = pd.Timestamp("2026-09-28 09:00"), pd.Timestamp("2026-09-28 10:00")
    current, peer = compare_peer(data, "London EC / Arran", start, end, True)
    assert current["Room key"] == "London EC / Arran"
    assert peer["Room key"] == "Oslo EC / Fjell"
    same_site = data.replace({"Room Name": {"Smaller": "Same size"}, "Room key": {"London EC / Smaller": "London EC / Same size"}})
    same_site.loc[same_site["Room Name"].eq("Same size"), "Capacity"] = 12
    assert compare_peer(same_site, "London EC / Arran", start, end, True)[1]["Room Name"] == "Same size"
    assert compare_peer(data[data["Room Name"].isin(["Arran", "Too small"])], "London EC / Arran", start, end, True) is None


def test_feedback_audience_filters_and_interactive_session_reset():
    at = app().switch_page("pages/Feedback.py").run()
    assert not at.exception, [e.message for e in at.exception]
    at.get("button_group")[0].set_value(AUDIENCES[1]).run()
    assert at.session_state["feedback_audience"] == AUDIENCES[1]
    assert any("Customer / guest" in h.value for h in at.markdown)
    submit = next(b for b in at.button if b.label == "Share feedback")
    submit.click().run()
    assert any("rate both" in w.value for w in at.warning)
    assert "feedback_tryouts" not in at.session_state
    groups = at.get("button_group")
    groups[1].set_value(AUDIENCES[1])
    groups[2].set_value(5)
    groups[3].set_value(4)
    next(b for b in at.button if b.label == "Share feedback").click().run()
    assert not at.exception, [e.message for e in at.exception]
    rows = at.session_state["feedback_tryouts"]
    assert len(rows) == 1 and rows[0]["audience"] == AUDIENCES[1] and rows[0]["is_demo"]
    assert rows[0]["source"] == "Interactive demonstration" and rows[0]["clock"] == "UTC"
    at.button(key="frame_it").click().run()
    assert any("No request has been sent" in i.value for i in at.info)
    at.button(key="frame_next").click().run()
    assert all(g.value is None for g in at.get("button_group")[1:])
    assert len(at.session_state["feedback_tryouts"]) == 1
    at.switch_page("pages/Frame.py").run()
    assert not at.exception
    assert len(at.get("button_group")) == 3
    at.switch_page("pages/Feedback.py").run()
    assert not at.exception
    assert at.session_state["feedback_audience"] == AUDIENCES[1]
    assert len(at.session_state["feedback_tryouts"]) == 1
