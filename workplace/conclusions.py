"""Evidence and planning inputs for the executive Overview.

No sentiment, empty time or equipment metadata is converted into cash savings.
Device highlights describe the current equipment of a room, not device usage.
"""
from hashlib import sha256
import re
import pandas as pd

from workplace.value import business_case

# Product/model mappings verified against Neat's Intune device-attributes guide:
# https://support.neat.no/article/neat-device-attributes-for-microsoft-intune-conditional-access-device-exclusions/
# Pad Pro is documented in Microsoft's Teams Android certified-hardware list:
# https://learn.microsoft.com/en-us/microsoftteams/devices/certified-hardware-android
MODEL_NAMES = {
    "NF19A1": "Neat Pad", "NF19B1": "Neat Bar", "NF22E1": "Neat Bar 2",
    "NF21D1": "Neat Bar Pro", "NF20C1": "Neat Board", "NF23K1": "Neat Board Pro",
    "NF22H1": "Neat Board 50", "NF21F1": "Neat Frame", "NF25J1": "Neat Pad Pro",
}
CONTROLLERS = {"NF19A1", "NF25J1"}


def room_type(capacity):
    """Analytical size bands, not a claim about the room's intended purpose."""
    if pd.isna(capacity) or capacity <= 0:
        return None
    for ceiling, label in [(2, "Focus · 1–2 seats"), (6, "Small · 3–6 seats"),
                           (12, "Medium · 7–12 seats")]:
        if capacity <= ceiling:
            return label
    return "Large · 13+ seats"


def eligible_rooms(ctx):
    s = ctx["stats"]
    return s[s["Coverage %"].ge(70) & s["Observed hours"].ge(2) & s.Capacity.gt(0)].copy()


def room_type_ranking(ctx):
    rooms = eligible_rooms(ctx)
    rooms["Room type"] = rooms.Capacity.map(room_type)
    grouped = rooms.groupby("Room type", as_index=False).agg(
        Rooms=("Room key", "nunique"), Observed=("Observed hours", "sum"),
        Occupied=("Occupied hours", "sum"))
    grouped["Time in use %"] = 100 * grouped.Occupied / grouped.Observed
    return grouped.sort_values(["Time in use %", "Room type"], ascending=[False, True]).reset_index(drop=True)


def leaders(ranking):
    """Report ties at displayed precision; never crown a zero-use group."""
    if ranking.empty or ranking["Time in use %"].max() <= 0:
        return ranking.iloc[:0]
    scores = ranking["Time in use %"].round(1)
    return ranking[scores.eq(scores.max())]


def equipment_details(raw):
    codes = sorted(set(c.strip() for c in re.split(r"\s*\+\s*", str(raw).upper()))) if pd.notna(raw) else []
    codes = [c for c in codes if c not in {"", "UNKNOWN", "NAN", "NONE"}]
    return {
        "video": [MODEL_NAMES[c] for c in codes if c in MODEL_NAMES and c not in CONTROLLERS],
        "other": [MODEL_NAMES[c] for c in codes if c in CONTROLLERS],
        "unmapped": [c for c in codes if c not in MODEL_NAMES],
    }


def leading_room(ctx):
    rooms = eligible_rooms(ctx).sort_values(["Utilisation %", "Room key"], ascending=[False, True])
    if rooms.empty or rooms.iloc[0]["Occupied hours"] <= 0:
        return None
    r = rooms.iloc[0].to_dict()
    r["joint"] = int(rooms["Utilisation %"].round(1).eq(round(r["Utilisation %"], 1)).sum()) > 1
    inv = ctx["inventory"].set_index("Room key").loc[r["Room key"]]
    r["equipment"] = equipment_details(inv.get("Neat Equipment"))
    r["equipment_timestamp"] = inv.get("Timestamp")
    return r


def improvement_summary(ctx):
    ready = ctx["stats"].loc[ctx["stats"]["Coverage %"].ge(70), "Room key"]
    issues = ctx["issues"][ctx["issues"]["Room key"].isin(ready)]
    counts = {kind: int(issues.loc[issues.Kind.eq(kind), "Room key"].nunique())
              for kind in ["fit", "warm", "light"]}
    return {"issues": issues, "counts": counts, "rooms": int(issues["Room key"].nunique()),
            "limited": int((ctx["stats"]["Coverage %"].fillna(0) < 70).sum())}


def conclusion(ctx, improvements):
    s, counts = ctx["summary"], improvements["counts"]
    if pd.isna(s["utilisation"]) or pd.isna(s["coverage"]) or s["coverage"] < 70:
        return ("Strengthen the evidence before committing to change.",
                "Close the observation gaps, then reassess room demand and the investment case.", "sunrise")
    if counts["fit"]:
        n = counts["fit"]
        return ("Review the room mix before adding more space.",
                f"{n} room{'s' if n != 1 else ''} had half their seats or fewer occupied for 90% of occupied time. "
                "Test smaller-room options against peak demand, then cost a pilot.", "forest")
    if counts["warm"] or counts["light"]:
        return ("Start with how your existing spaces are run.",
                "Repeated conditions in empty rooms warrant a facilities review. Check controls and actual energy use to quantify the benefit.", "forest")
    return ("Use the strongest room patterns to guide your next decision.",
            "No improvement findings pass the current review rules. Compare room demand and gather real feedback before changing the estate.", "rain")


def planning_cases(state, rooms):
    """Separate room/currency cases. Never add potentially overlapping projects."""
    cases = []
    for room in sorted(set(rooms)):
        for currency in ["GBP", "EUR", "NOK"]:
            token = sha256(room.encode()).hexdigest()[:12] + "_" + currency
            values = [state.get(f"value_{token}_{name}") for name in ["project", "savings", "extra"]]
            result = business_case(*values, state.get(f"value_{token}_years", 3))
            if result is not None:
                cases.append({"id": token, "room": room, "currency": currency,
                              "example": bool(state.get(f"value_{token}_example", False)), **result})
    return cases
