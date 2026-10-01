"""Room-size counterfactuals using observed occupied time, never booking demand."""
from __future__ import annotations

from math import isfinite

import pandas as pd

from workplace.analytics import weighted_quantile


ASSUMPTIONS = [
    "Replay the selected room's observed people counts without changing attendance.",
    "Treat each observed count as one group requiring one room; do not split it across rooms.",
    "For two proposed rooms, test against the larger room. Total seats do not determine fit.",
    "A second room's future use and simultaneous demand cannot be inferred from this feed.",
    "Exclude empty, missing and offline time from the fit percentage. Missing time stays unknown.",
    "Room dimensions, partitions, acoustics, accessibility, bookings and AV requirements need a separate review.",
    "Project costs are user-entered assumptions. No energy savings, revenue or payback is calculated.",
]


def room_evidence(samples, room_key, expected_hours):
    selected = samples.loc[samples["Room key"].eq(room_key)].copy()
    valid = selected.loc[selected["Valid hours"].gt(0) & selected.Occupancy.notna()]
    occupied = valid.loc[valid.Occupancy.gt(0)].copy()
    observed_hours = float(valid["Valid hours"].sum())
    occupied_hours = float(occupied["Occupied hours"].sum())
    return dict(
        occupied=occupied, observed_hours=observed_hours, occupied_hours=occupied_hours,
        empty_hours=max(0.0, observed_hours - occupied_hours),
        unknown_hours=max(0.0, expected_hours - observed_hours), expected_hours=expected_hours,
        coverage=min(100.0, 100 * observed_hours / expected_hours) if expected_hours > 0 else None,
        typical=float(occupied["Person hours"].sum() / occupied_hours) if occupied_hours else None,
        p90=weighted_quantile(occupied.Occupancy, occupied["Occupied hours"]) if occupied_hours else None,
        peak=float(occupied.Occupancy.max()) if occupied_hours else None,
    )


def evaluate_layout(evidence, capacities, project_cost=None):
    capacities = tuple(capacities)
    if not 1 <= len(capacities) <= 2:
        raise ValueError("Specify one or two rooms.")
    if any(isinstance(n, bool) or not isfinite(n) or n <= 0 or int(n) != n for n in capacities):
        raise ValueError("Each room needs a positive whole-number capacity.")
    if project_cost is not None and (not isfinite(project_cost) or project_cost < 0):
        raise ValueError("Project cost must be blank or a non-negative number.")
    occupied = evidence["occupied"]
    total = evidence["occupied_hours"]
    largest = max(capacities)
    fits = float(occupied.loc[occupied.Occupancy.le(largest), "Occupied hours"].sum())
    return dict(capacities=list(map(int, capacities)), rooms=len(capacities),
                total_seats=int(sum(capacities)), largest_room=int(largest),
                fit_percent=100 * fits / total if total else None,
                fits_hours=fits if total else None,
                exceeds_hours=max(0.0, total - fits) if total else None,
                project_cost=project_cost)


def attendance_bands(evidence):
    occupied = evidence["occupied"]
    total = evidence["occupied_hours"]
    bands = [(0, 2, "1-2"), (2, 4, "3-4"), (4, 6, "5-6"),
             (6, 8, "7-8"), (8, 12, "9-12"), (12, float("inf"), "13+")]
    rows = []
    for low, high, label in bands:
        hours = float(occupied.loc[occupied.Occupancy.gt(low) & occupied.Occupancy.le(high), "Occupied hours"].sum())
        rows.append(dict(people=label, hours=hours, percent=100 * hours / total if total else None))
    return pd.DataFrame(rows)


def export_comparison(ctx, room, evidence, layouts, currency):
    rows = []
    for label, result in layouts:
        rows.append({
            "Option": label, "Room": room, "Period start": ctx["start"].isoformat(),
            "Period end": ctx["end"].isoformat(), "Clock": "Recorded source time",
            "Operating hours": "Weekdays 08:00-19:00" if ctx["office"] else "All hours",
            "Source": "Generated demonstration data" if ctx.get("demo") else "Pulse reporting feed",
            "Proposed room capacities": " + ".join(map(str, result["capacities"])),
            "Number of rooms": result["rooms"], "Total seats": result["total_seats"],
            "Largest room": result["largest_room"], "Fit % of occupied time": result["fit_percent"],
            "Occupied hours exceeding largest room": result["exceeds_hours"],
            "Observed occupied hours": evidence["occupied_hours"], "Coverage %": evidence["coverage"],
            "Unknown hours": evidence["unknown_hours"], "Observed peak people": evidence["peak"],
            "Entered project cost": result["project_cost"], "Currency": currency,
            "Cost basis": "No layout-change project" if label == "Current" else "User assumption; blank means unknown",
            "Assumptions": " ".join(ASSUMPTIONS),
        })
    return pd.DataFrame(rows)
