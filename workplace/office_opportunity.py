"""Office-wide scenarios: observations, conceptual rooms and costs stay separate."""
from hashlib import sha256
import math
from workplace import analytics as a, conclusions as x
from workplace.scenarios import room_evidence, evaluate_layout
from workplace.value import business_case
from workplace.office_map import SPACES


def scope_rooms(ctx):
    rooms = ctx["stats"].copy()
    assets = {"London EC / " + n for s in SPACES if s["kind"] != "room" for n in s["sources"]}
    return rooms[rooms.Capacity.gt(0) & rooms.Capacity.mod(1).eq(0)
                 & ~rooms["Room key"].isin(assets)].drop_duplicates("Room key").copy()


def opportunities(ctx):
    rooms = scope_rooms(ctx)
    ready = rooms[rooms["Coverage %"].ge(70) & rooms["Observed hours"].ge(2)]
    issues = x.improvement_summary(ctx)["issues"]
    controls = sorted(set(issues.loc[issues.Kind.isin(["warm", "light"]), "Room key"]) & set(ready["Room key"]))
    candidates = ready[ready["Room key"].isin(issues.loc[issues.Kind.eq("fit"), "Room key"])
                       & ready.Capacity.ge(8) & ready["Occupied hours"].ge(2)]
    protected = []
    for _, group in rooms.groupby(rooms["Room key"].str.rsplit(" / ", n=1).str[0]):
        protected.append(group.sort_values(["Capacity", "Room key"], ascending=[False, True]).iloc[0]["Room key"])
    candidates = candidates[~candidates["Room key"].isin(protected)].sort_values(
        ["Capacity", "Room key"], ascending=[False, True])
    return dict(rooms=rooms, ready=ready, controls=controls, candidates=candidates, protected=protected,
                token=sha256("|".join(sorted(rooms["Room key"])).encode()).hexdigest()[:12])


def room_mix(capacities):
    return [sum(low <= n <= high for n in capacities)
            for low, high in [(1, 2), (3, 6), (7, 12), (13, float("inf"))]]


def programme_costs(controls, additional, assumptions):
    """One programme budget; never sum overlapping room cases or sensor hours."""
    if not assumptions or not (controls or additional):
        return None
    names = ("gross", "running", "control_project", "split_project", "extra_running")
    values = {name: assumptions[name] for name in names}
    if any(isinstance(v, bool) or not math.isfinite(v) or v < 0 for v in values.values()):
        raise ValueError("Programme assumptions must be finite, non-negative amounts.")
    project = controls * values["control_project"] + additional * values["split_project"]
    gross = controls * values["gross"]
    running = controls * values["running"] + additional * values["extra_running"]
    return {**business_case(project, gross, running, 3), "currency": "GBP",
            "illustrative": assumptions.get("illustrative", True)}


def office_scenario(ctx, split_rooms=(), seats=None, assumptions=None):
    model = opportunities(ctx)
    selected = set(split_rooms) & set(model["candidates"]["Room key"])
    seats = seats or {}
    expected = a.window_hours(ctx["start"], ctx["end"], ctx["office"])
    ready = set(model["ready"]["Room key"])
    current, proposed, details = [], [], []
    occupied = fits = exceeds = 0.0
    for _, row in model["rooms"].iterrows():
        key, capacity = row["Room key"], int(row.Capacity)
        current.append(capacity)
        caps = [capacity]
        if key in selected:
            first = seats.get(key, capacity // 2)
            if isinstance(first, bool) or not isinstance(first, (int, float)) or not math.isfinite(first) or int(first) != first or not 1 <= first < capacity:
                raise ValueError("The first concept room must have fewer seats than the original room.")
            caps = [int(first), capacity - int(first)]
        proposed.extend(caps)
        if key not in ready:
            continue
        evidence = room_evidence(ctx["samples"], key, expected)
        replay = evaluate_layout(evidence, caps)
        occupied += evidence["occupied_hours"]
        fits += replay["fits_hours"] or 0
        exceeds += replay["exceeds_hours"] or 0
        if key in selected:
            details.append(dict(room=key, name=row["Room Name"], before=capacity, after=caps,
                                fit=replay["fit_percent"], exceeds=replay["exceeds_hours"], peak=evidence["peak"]))
    return {**model, "splits": details, "additional": len(details), "before_count": len(current),
            "after_count": len(proposed), "before_mix": room_mix(current), "after_mix": room_mix(proposed),
            "fit": 100 * fits / occupied if occupied else None, "occupied": occupied, "exceeds": exceeds,
            "costs": programme_costs(len(model["controls"]), len(details), assumptions)}
