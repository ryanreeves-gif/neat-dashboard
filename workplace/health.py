"""Local sign-in event replay; not a webhook receiver or vendor payload contract."""
from hashlib import sha256
import json

import pandas as pd


def scope_key(ctx, room):
    inventory = ctx["inventory"].sort_values("Room key")
    scope = dict(room=room, start=str(ctx["start"]), end=str(ctx["end"]),
                 office=ctx["office"], demo=ctx.get("demo", False),
                 rooms=inventory[["Room key", "Platform", "Device Status", "Timestamp"]].astype(str).values.tolist())
    return sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()


def replay_events(room, start, end, stage):
    """Invented ordered events placed within the selected recorded-clock window."""
    if stage not in (0, 1, 2) or end <= start:
        raise ValueError("A replay needs a valid stage and a positive date window.")
    states = ["Signed in", "Signed out", "Signed in"]
    return [dict(event_id=f"demo-{i}", room_key=room, state=states[i],
                 occurred_at=(start + (end - start) * ((i + 1) / 4)).isoformat(),
                 source="Simulation") for i in range(stage + 1)]


def latest_signin(events, room, as_of):
    """No event means unknown; only an explicit later event can clear sign-out."""
    valid = [e for e in events if e["room_key"] == room and pd.Timestamp(e["occurred_at"]) <= as_of]
    if not valid:
        return "Unknown"
    latest = max(valid, key=lambda e: pd.Timestamp(e["occurred_at"]))
    return latest["state"] if latest["state"] in ("Signed in", "Signed out") else "Unknown"


def current_demo(ctx, session):
    saved = session.get("health_demo")
    if not saved:
        return None
    room = saved["room"]
    eligible = ctx["inventory"].query("Platform == 'Microsoft Teams'")["Room key"]
    if room not in set(eligible) or saved["scope"] != scope_key(ctx, room):
        return None
    return saved


def make_demo(ctx, room, stage):
    if room not in set(ctx["inventory"].query("Platform == 'Microsoft Teams'")["Room key"]):
        raise ValueError("Select a Microsoft Teams room in the current scope.")
    events = replay_events(room, ctx["start"], ctx["end"], stage)
    return dict(room=room, scope=scope_key(ctx, room), stage=stage, events=events,
                status=latest_signin(events, room, ctx["end"]), source="Simulation",
                command_sent=False, ticket_created=False)
