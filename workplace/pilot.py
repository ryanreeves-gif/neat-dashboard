"""Scoped pilot proposals. Observations support investigation, never approval or ROI."""
import pandas as pd

from workplace import conclusions as x


def pilot_options(ctx, room):
    row = ctx["stats"].set_index("Room key").loc[room]
    if pd.isna(row["Coverage %"]) or row["Coverage %"] < 70 or row["Observed hours"] < 2:
        return ["Evidence baseline"]
    findings = x.improvement_summary(ctx)["issues"]
    kinds = set(findings.loc[findings["Room key"].eq(room), "Kind"])
    options = []
    if kinds & {"warm", "light"}:
        options.append("Operating schedules")
    if "fit" in kinds:
        options.append("Room layout")
    return options or ["Evidence baseline"]


def pilot_plan(ctx, room, focus=None):
    options = pilot_options(ctx, room)
    focus = focus if focus in options else options[0]
    row = ctx["stats"].set_index("Room key").loc[room]
    plans = {
        "Room layout": dict(
            title="Test a smaller-room layout", owner="Workplace + IT / AV",
            action="Trial a reversible layout that suits the groups using the room.",
            gate="Confirm bookings, peak groups, room purpose and accessibility.",
            measure="Compare room use, unmet demand and real feedback.",
            benefit="Better space allocation", cost="Design, furniture, AV and any building work",
            baseline="Observed attendance and capacity; bookings still needed",
            success="The room serves its intended groups; peak demand is accommodated elsewhere.",
        ),
        "Operating schedules": dict(
            title="Check the room's running schedule", owner="Facilities + IT / BMS",
            action="Trial one approved schedule change in this room.",
            gate="Confirm when the room is empty and what is actually running.",
            measure="Compare actual energy use and comfort before and after.",
            benefit="Potential operating efficiency", cost="Integration, commissioning and ongoing support",
            baseline="Observed conditions; controller state and energy baseline still needed",
            success="Actual energy or cost improves while comfort and room availability are protected.",
        ),
        "Evidence baseline": dict(
            title="Collect more evidence first", owner="Workplace + IT + Facilities",
            action="Collect a representative period of room use and feedback.",
            gate="Confirm sensor reporting and what the room is meant to support.",
            measure="Review coverage, booking demand and real feedback.",
            benefit="A more reliable investment decision", cost="Data collection and measurement effort",
            baseline="Validate observations and collect the missing demand and experience data",
            success="Enough representative evidence exists to choose and cost a specific intervention.",
        ),
    }
    return {"room": room, "name": row["Room Name"], "focus": focus,
            "coverage": row["Coverage %"], "source": "Sample telemetry" if ctx.get("demo") else "Pulse observations",
            **plans[focus]}


def scoped_case(case, room):
    """An estate-level selection must never become another room's forecast."""
    return case if case and not case.get("example") and case.get("room") == room else None
