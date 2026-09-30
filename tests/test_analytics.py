import numpy as np
import pandas as pd
import pytest
from workplace import analytics as a


def source(times, occupancy, **extra):
    n = len(times)
    return pd.DataFrame({"Timestamp": times, "Room Name": ["A"] * n, "Location": ["London"] * n,
                         "Device Status": ["Online"] * n, "Occupancy": occupancy, "Capacity": [8] * n, **extra})


def test_existing_source_date_migration():
    result = a.parse_timestamps(pd.Series(["4/9/2026 14:04:25", "9/10/2026 11:55:32", "10/09/2026 12:41:06", "30/09/2026 13:00:06", "bad"]))
    assert result.iloc[0] == pd.Timestamp("2026-04-09 14:04:25")
    assert result.iloc[1] < result.iloc[2]
    assert result.iloc[2] == pd.Timestamp("2026-09-10 12:41:06")
    assert result.iloc[3].month == 9
    assert pd.isna(result.iloc[4])


def test_missing_values_and_location_identity():
    raw = source(["2026-09-28 09:00", "2026-09-28 09:10", "2026-09-28 09:00"], [None, 0, 2],
                 Location=["London", "London", "Oslo"], Capacity=[8, None, None], Temperature=[None, 21, 20])
    d, _ = a.prepare(raw)
    assert d["Room key"].nunique() == 2
    assert d.loc[d.Location == "London", "Capacity"].tolist() == [8, 8]
    assert d.loc[d.Location == "Oslo", "Capacity"].isna().all()
    assert d.Temperature.isna().sum() == 1
    assert d.Occupancy.isna().sum() == 1


def test_time_weighting_and_missing_offline_exclusion():
    raw = source(pd.date_range("2026-09-28 09:00", periods=5, freq="10min").astype(str), [2, 0, np.nan, 0, 4],
                 **{"Device Status": ["Online", "Online", "Online", "Offline", "Online"]})
    d, _ = a.prepare(raw)
    seg = a.intervals(d, pd.Timestamp("2026-09-28 09:00"), pd.Timestamp("2026-09-28 09:50"), True)
    s = a.summarise(seg, 50 / 60, 1)
    assert s["valid_hours"] == pytest.approx(.5)
    assert s["utilisation"] == pytest.approx(200 / 3)
    assert s["attendance"] == pytest.approx(3)
    assert s["coverage"] == pytest.approx(60)


def test_long_gaps_are_not_filled_and_heatmap_reconciles():
    raw = source(["2026-09-28 09:50", "2026-09-28 10:05", "2026-09-28 10:20", "2026-09-28 15:00"], [2, 0, 4, 0])
    d, _ = a.prepare(raw)
    seg = a.intervals(d, pd.Timestamp("2026-09-28 09:50"), pd.Timestamp("2026-09-28 15:15"), True)
    assert seg["Valid hours"].sum() == pytest.approx(1)
    assert seg["Occupied hours"].sum() == pytest.approx(.5)
    assert ((seg.End - seg.Start).dt.total_seconds() <= 900).all()
    _, _, z, hours = a.heatmap(seg, True)
    assert hours.sum() == pytest.approx(seg["Valid hours"].sum())
    assert np.nansum(z * hours / 100) == pytest.approx(seg["Occupied hours"].sum())


def test_office_boundary_and_weekend():
    d, _ = a.prepare(source(["2026-09-25 18:55", "2026-09-25 19:05", "2026-09-26 09:00"], [2, 2, 2]))
    seg = a.intervals(d, pd.Timestamp("2026-09-25 18:00"), pd.Timestamp("2026-09-26 12:00"), True)
    assert seg["Valid hours"].sum() == pytest.approx(5/60)
    assert a.window_hours(pd.Timestamp("2026-09-25 18:00"), pd.Timestamp("2026-09-28 09:00"), True) == 2


def test_empty_and_unknown_are_not_reported_as_zero_utilisation():
    d, _ = a.prepare(source(["2026-09-28 09:00"], [np.nan]))
    seg = a.intervals(d, pd.Timestamp("2026-09-28 09:00"), pd.Timestamp("2026-09-28 09:10"), True)
    s = a.summarise(seg, 1/6, 1)
    assert np.isnan(s["utilisation"])
    assert np.isnan(s["attendance"])
    assert s["coverage"] == 0


def test_findings_require_evidence_and_preserve_uncertainty():
    d, _ = a.prepare(source(pd.date_range("2026-09-28 09:00", periods=12, freq="10min").astype(str), [0]*12,
                           Temperature=[23]*12, **{"Light Level": [np.nan]*12}))
    start, end = pd.Timestamp("2026-09-28 09:00"), pd.Timestamp("2026-09-28 11:00")
    seg = a.intervals(d, start, end, True)
    rooms = a.room_statistics(seg, a.inventory(d), 2)
    findings = a.findings(seg, rooms)
    assert findings.Kind.tolist() == ["warm"]
    assert findings.iloc[0]["Evidence hours"] == pytest.approx(2)
    assert a.findings(seg, rooms, min_hours=3).empty
    assert "savings are not established" in findings.iloc[0]["Why it matters"]


def test_room_fit_excludes_empty_time_and_uses_p90():
    values = [0]*6 + [2]*12
    d, _ = a.prepare(source(pd.date_range("2026-09-28 09:00", periods=18, freq="10min").astype(str), values))
    seg = a.intervals(d, pd.Timestamp("2026-09-28 09:00"), pd.Timestamp("2026-09-28 12:00"), True)
    rooms = a.room_statistics(seg, a.inventory(d), 3)
    assert rooms.iloc[0]["Typical attendance"] == 2
    assert rooms.iloc[0]["P90 attendance"] == 2
    assert a.findings(seg, rooms).Kind.tolist() == ["fit"]


def test_duplicate_rows_do_not_double_count():
    raw = source(["2026-09-28 09:00"]*2, [1, 2])
    d, quality = a.prepare(raw)
    assert len(d) == 1 and d.iloc[0].Occupancy == 2
    assert quality["duplicates"] == 1
