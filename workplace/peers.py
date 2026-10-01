"""Automatic capacity peers, independent of the dashboard's room filter."""
import pandas as pd
from workplace import analytics as a


def compare_peer(data, room_key, start, end, office):
    inventory = a.inventory(data[data.Timestamp.le(end)])
    selected = inventory[inventory["Room key"].eq(room_key)]
    if selected.empty or pd.isna(selected.iloc[0].Capacity) or selected.iloc[0].Capacity <= 0:
        return None
    room = selected.iloc[0]
    candidates = inventory[inventory.Timestamp.ge(start) & inventory.Capacity.gt(0)
                           & inventory["Room key"].ne(room_key)].copy()
    # No implausible match: at most 25% or two seats away.
    candidates["seat_gap"] = (candidates.Capacity - room.Capacity).abs()
    candidates = candidates[candidates.seat_gap.le(max(2, room.Capacity * .25))]
    if candidates.empty:
        return None
    nearest = candidates.seat_gap.min()
    candidates = candidates[candidates.seat_gap.eq(nearest)]
    candidates["other_location"] = candidates.Location.ne(room.Location)
    candidates = candidates[candidates.other_location.eq(candidates.other_location.min())]
    keys = candidates["Room key"].tolist() + [room_key]
    samples = a.intervals(data[data["Room key"].isin(keys)], start, end, office)
    stats = a.room_statistics(samples, inventory[inventory["Room key"].isin(keys)], a.window_hours(start, end, office))
    peer = stats[stats["Room key"].ne(room_key)].sort_values(
        ["Coverage %", "Observed hours", "Room key"], ascending=[False, False, True], na_position="last").iloc[0]
    current = stats[stats["Room key"].eq(room_key)].iloc[0]
    return current, peer
