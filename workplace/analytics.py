"""Pure, time-weighted calculations. Unknown readings are never empty rooms."""
from __future__ import annotations

from datetime import date, timedelta
import numpy as np
import pandas as pd

KEY = ["Location", "Room Name"]
SENSORS = ["Occupancy", "Temperature", "Humidity", "VOC", "Light Level"]
PLATFORMS = {"msteams": "Microsoft Teams", "zoom": "Zoom", "google_meet": "Google Meet",
             "apphub": "Neat App Hub", "usb": "BYOD", "avos": "Neat Open / partner app",
             "none": "Unprovisioned", "oob": "Not configured"}


def parse_timestamps(values: pd.Series, date_order: str = "legacy_mixed") -> pd.Series:
    """The existing sheet changed from unpadded US to padded UK dates on 10 Sep.

    Keep this source-specific migration explicit, rather than guessing a single
    dayfirst setting for the entire file. ISO dates are parsed independently.
    All clocks stay in the source's recorded time; no timezone is invented.
    """
    s = values.astype("string").str.strip()
    iso = s.str.match(r"^\d{4}-", na=False)
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    out.loc[iso] = pd.to_datetime(s[iso], format="mixed", errors="coerce", utc=True).dt.tz_localize(None)
    slash = ~iso
    if date_order == "legacy_mixed":
        padded = s.str.match(r"^\d{2}/\d{2}/\d{4}", na=False)
        # Unambiguous day >12 is UK even when a replacement source is unpadded.
        first = pd.to_numeric(s.str.extract(r"^(\d{1,2})/", expand=False), errors="coerce")
        uk = padded | first.gt(12)
        for mask, dayfirst in [(slash & uk, True), (slash & ~uk, False)]:
            out.loc[mask] = pd.to_datetime(s[mask], format="mixed", dayfirst=dayfirst, errors="coerce")
    elif date_order in {"dayfirst", "monthfirst"}:
        out.loc[slash] = pd.to_datetime(s[slash], format="mixed", dayfirst=date_order == "dayfirst", errors="coerce")
    elif date_order != "iso":
        raise ValueError("DATE_ORDER must be legacy_mixed, dayfirst, monthfirst or iso.")
    return out


def prepare(raw: pd.DataFrame, date_order: str = "legacy_mixed") -> tuple[pd.DataFrame, dict]:
    d = raw.copy()
    d.columns = d.columns.str.strip()
    required = ["Timestamp", *KEY]
    missing = [c for c in required if c not in d]
    if missing:
        raise ValueError("Missing required CSV columns: " + ", ".join(missing))
    d["Timestamp"] = parse_timestamps(d["Timestamp"], date_order)
    invalid = int(d["Timestamp"].isna().sum())
    d = d.dropna(subset=["Timestamp"])
    for c in KEY:
        d[c] = d[c].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
    for c in [*SENSORS, "Capacity", "Offline Minutes"]:
        d[c] = pd.to_numeric(d[c], errors="coerce") if c in d else np.nan
        d[c] = d[c].replace([np.inf, -np.inf], np.nan)
    for c in ["Occupancy", "VOC", "Light Level"]:
        d.loc[d[c] < 0, c] = np.nan
    d.loc[~d["Humidity"].between(0, 100), "Humidity"] = np.nan
    d.loc[d["Capacity"] < 0, "Capacity"] = np.nan
    for c in ["Platform", "Software Version", "Notes", "Air Quality"]:
        if c not in d:
            d[c] = "Unknown"
        d[c] = d[c].fillna("Unknown").astype(str)
    d["Platform"] = d["Platform"].replace(PLATFORMS)
    if "Device Status" not in d:
        d["Device Status"] = "Unreported"
    d["Device Status"] = d["Device Status"].fillna("Unknown").astype(str).str.strip().str.title()
    before = len(d)
    d = d.sort_values("Timestamp", kind="stable").drop_duplicates(KEY + ["Timestamp"], keep="last")
    d = d.sort_values(KEY + ["Timestamp"]).reset_index(drop=True)
    d["Room key"] = d["Location"] + " / " + d["Room Name"]
    # Latest known metadata for the same named room, never an invented 4-seat default.
    d["Capacity"] = d.groupby(KEY)["Capacity"].transform(lambda s: s.ffill().bfill())
    return d, {"rows": len(raw), "invalid_dates": invalid, "duplicates": before - len(d),
               "date_order": date_order, "status_unreported": bool(d["Device Status"].eq("Unreported").any())}


def inventory(data: pd.DataFrame) -> pd.DataFrame:
    return data.sort_values("Timestamp").drop_duplicates(KEY, keep="last").copy()


def window_hours(start: pd.Timestamp, end: pd.Timestamp, office: bool) -> float:
    if end <= start:
        return 0.0
    if not office:
        return (end - start).total_seconds() / 3600
    total = 0.0
    for day in pd.date_range(start.normalize(), end.normalize(), freq="D"):
        if day.dayofweek < 5:
            a, b = max(start, day + pd.Timedelta(hours=8)), min(end, day + pd.Timedelta(hours=19))
            total += max(0, (b - a).total_seconds() / 3600)
    return total


def intervals(data: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, office: bool) -> pd.DataFrame:
    """Hold each sample until the next sample, capped at its observed cadence.

    A gap is never filled indefinitely. Infer cadence per room within the chosen
    window (bounded 1–30 min); fall back to 10 min for isolated observations.
    Split intervals at hour boundaries so the heatmap and totals agree exactly.
    """
    d = data[(data.Timestamp >= start - pd.Timedelta(minutes=30)) & (data.Timestamp < end)].copy()
    if d.empty:
        for c in ["Hours", "Occupied hours", "Valid hours", "Person hours"]:
            d[c] = pd.Series(dtype=float)
        d["Start"] = pd.Series(dtype="datetime64[ns]")
        d["End"] = pd.Series(dtype="datetime64[ns]")
        return d
    d = d.sort_values(KEY + ["Timestamp"])
    nxt = d.groupby(KEY)["Timestamp"].shift(-1)
    gap = (nxt - d.Timestamp).dt.total_seconds()
    d["Cadence"] = gap.where(gap.between(30, 1800))
    d["Cadence"] = d.groupby(KEY)["Cadence"].transform("median").fillna(600).clip(60, 1800)
    proposed = d.Timestamp + pd.to_timedelta(d.Cadence, unit="s")
    d["End"] = pd.concat([proposed, nxt], axis=1).min(axis=1).clip(upper=end)
    d["Start"] = d.Timestamp.clip(lower=start)
    if office:
        day = d.Timestamp.dt.normalize()
        d["Start"] = pd.concat([d.Start, day + pd.Timedelta(hours=8)], axis=1).max(axis=1)
        d["End"] = pd.concat([d.End, day + pd.Timedelta(hours=19)], axis=1).min(axis=1)
        d = d[d.Timestamp.dt.dayofweek < 5].copy()
    d = d[d.End > d.Start].copy()
    boundary = d.Start.dt.floor("h") + pd.Timedelta(hours=1)
    cross = d.End > boundary
    tail = d[cross].copy()
    tail["Start"] = boundary[cross]
    d.loc[cross, "End"] = boundary[cross]
    d = pd.concat([d, tail], ignore_index=True)
    d["Hours"] = (d.End - d.Start).dt.total_seconds() / 3600
    valid = d["Occupancy"].notna() & d["Device Status"].isin(["Online", "Unreported"])
    d["Valid hours"] = d.Hours.where(valid, 0)
    d["Occupied hours"] = d.Hours.where(valid & d.Occupancy.gt(0), 0)
    d["Person hours"] = (d.Occupancy * d.Hours).where(valid & d.Occupancy.gt(0), 0)
    return d


def weighted_quantile(values: pd.Series, weights: pd.Series, q: float = .9) -> float:
    valid = values.notna() & weights.gt(0)
    if not valid.any():
        return np.nan
    v = pd.DataFrame({"v": values[valid], "w": weights[valid]}).sort_values("v")
    return float(v.loc[v.w.cumsum() >= q * v.w.sum(), "v"].iloc[0])


def summarise(samples: pd.DataFrame, hours: float, room_count: int) -> dict:
    valid = float(samples["Valid hours"].sum())
    occupied = float(samples["Occupied hours"].sum())
    expected = hours * room_count
    return {"rooms": room_count, "valid_hours": valid, "occupied_hours": occupied,
            "utilisation": 100 * occupied / valid if valid > 0 else np.nan,
            "attendance": samples["Person hours"].sum() / occupied if occupied > 0 else np.nan,
            "coverage": min(100, 100 * valid / expected) if expected > 0 else np.nan,
            "expected_hours": expected}


def room_statistics(samples: pd.DataFrame, room_inventory: pd.DataFrame, scheduled_hours: float) -> pd.DataFrame:
    out = []
    for _, room in room_inventory.iterrows():
        s = samples[samples["Room key"] == room["Room key"]]
        valid, occ = s["Valid hours"].sum(), s["Occupied hours"].sum()
        out.append({**{k: room[k] for k in [*KEY, "Room key", "Capacity", "Platform", "Device Status", "Timestamp"]},
                    "Observed hours": valid, "Occupied hours": occ,
                    "Utilisation %": 100 * occ / valid if valid > 0 else np.nan,
                    "Typical attendance": s["Person hours"].sum() / occ if occ > 0 else np.nan,
                    "P90 attendance": weighted_quantile(s.Occupancy, s["Occupied hours"]),
                    "Coverage %": min(100, 100 * valid / scheduled_hours) if scheduled_hours > 0 else np.nan})
    return pd.DataFrame(out)


def findings(samples: pd.DataFrame, rooms: pd.DataFrame, warm: float = 22, bright: float = 50,
             min_hours: float = 1) -> pd.DataFrame:
    rows = []
    for _, r in rooms.iterrows():
        s = samples[samples["Room key"] == r["Room key"]]
        empty = s["Valid hours"].gt(0) & s.Occupancy.eq(0)
        for kind, sensor, threshold, observation, next_step in [
            ("warm", "Temperature", warm, "Warm while empty", "Check HVAC operating state and room conditions"),
            ("light", "Light Level", bright, "Bright while empty", "Check lighting state and daylight contribution")]:
            hours = s.loc[empty & s[sensor].gt(threshold), "Hours"].sum()
            if hours >= min_hours:
                unit = "°C" if kind == "warm" else "lx"
                rows.append({"Room": r["Room Name"], "Location": r.Location, "Room key": r["Room key"],
                             "Finding": observation, "Evidence": f"{hours:.1f} observed hours above {threshold:g} {unit}",
                             "Why it matters": "A recurring condition worth checking; equipment activity and savings are not established.",
                             "Next step": next_step, "Owner": "Facilities", "Kind": kind,
                             "Evidence hours": hours, "Rank": hours})
        if pd.notna(r.Capacity) and r.Capacity >= 4 and r["Occupied hours"] >= 2 and r["P90 attendance"] <= .5 * r.Capacity:
            rows.append({"Room": r["Room Name"], "Location": r.Location, "Room key": r["Room key"],
                         "Finding": "Small groups in a large room",
                         "Evidence": f"90% of observed occupied time: ≤{r['P90 attendance']:.0f} people / {r.Capacity:.0f} seats",
                         "Why it matters": "Review the room mix against peak demand before changing capacity.",
                         "Next step": "Review room-size demand over a representative period", "Owner": "Workplace",
                         "Kind": "fit", "Evidence hours": r["Occupied hours"], "Rank": r["Occupied hours"]})
    columns = ["Room", "Location", "Room key", "Finding", "Evidence", "Why it matters", "Next step", "Owner", "Kind", "Evidence hours", "Rank"]
    return pd.DataFrame(rows, columns=columns).sort_values(["Rank", "Room key"], ascending=[False, True]).reset_index(drop=True)


def heatmap(samples: pd.DataFrame, office: bool) -> tuple[list, list, np.ndarray, np.ndarray]:
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"] if office else ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    bands = [("Morning", 8, 12), ("Midday", 12, 15), ("Afternoon", 15, 19)] if office else [("Night", 0, 6), ("Morning", 6, 12), ("Afternoon", 12, 18), ("Evening", 18, 24)]
    z = np.full((len(bands), len(days)), np.nan)
    coverage = np.zeros_like(z)
    if samples.empty:
        return days, [x[0] for x in bands], z, coverage
    for i, (_, a, b) in enumerate(bands):
        for j in range(len(days)):
            s = samples[(samples.Start.dt.dayofweek == j) & samples.Start.dt.hour.between(a, b - 1)]
            valid = s["Valid hours"].sum()
            coverage[i, j] = valid
            if valid:
                z[i, j] = 100 * s["Occupied hours"].sum() / valid
    return days, [x[0] for x in bands], z, coverage


def demo_data() -> pd.DataFrame:
    """Explicit opt-in demonstration; never substituted for a failed live feed."""
    end = pd.Timestamp.now().floor("10min")
    times = pd.date_range(end.normalize() - pd.Timedelta(days=13), end, freq="10min")
    rows = []
    for j, (name, capacity) in enumerate([("Arran", 12), ("Barra", 7), ("Harris", 5), ("Longrow", 5)]):
        for t in times:
            busy = t.dayofweek < 5 and 9 <= t.hour < 17 and (t.hour + j + t.day) % 4 != 0
            people = (2 + (t.hour + j) % 3) if busy else 0
            rows.append({"Timestamp": t.isoformat(), "Room Name": name, "Location": "Example office",
                         "Device Status": "Online", "Occupancy": people, "Capacity": capacity,
                         "Temperature": 23 if j == 0 else 21, "Humidity": 45,
                         "Light Level": 140 if 7 <= t.hour < 20 else 5, "VOC": 110,
                         "Platform": "msteams" if j % 2 else "zoom"})
    return pd.DataFrame(rows)
