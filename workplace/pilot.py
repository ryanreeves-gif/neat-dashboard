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
    if "fit" in kinds:
        options.append("Room layout")
    if kinds & {"warm", "light"}:
        options.append("Operating schedules")
    return options or ["Evidence baseline"]


def pilot_plan(ctx, room, focus=None):
    options = pilot_options(ctx, room)
    focus = focus if focus in options else options[0]
    row = ctx["stats"].set_index("Room key").loc[room]
    plans = {
        "Room layout": dict(
            title="Validate a smaller-room pilot", owner="Workplace + IT / AV",
            action="Trial a reversible layout after checking peak demand and room purpose.",
            gate="Check bookings, unmet demand, peak groups, accessibility, acoustics and AV.",
            measure="Track capacity exceptions, room use and genuine feedback.",
            benefit="Better space allocation", cost="Design, furniture, AV and any building work",
            baseline="Observed attendance and capacity; bookings still needed",
            success="The room serves its intended groups; peak demand is accommodated elsewhere.",
        ),
        "Operating schedules": dict(
            title="Validate an operating-schedule pilot", owner="Facilities + IT / BMS",
            action="Check actual plant and lighting state; trial one permitted schedule change.",
            gate="Confirm vacancy, bookings, daylight, room-to-zone mapping and comfort limits.",
            measure="Track comfort, qualifying condition hours and metered energy.",
            benefit="Potential operating efficiency", cost="Integration, commissioning and ongoing support",
            baseline="Observed conditions; controller state and energy baseline still needed",
            success="Actual energy or cost improves while comfort and room availability are protected.",
        ),
        "Evidence baseline": dict(
            title="Build the evidence before changing the room", owner="Workplace + IT + Facilities",
            action="Confirm reporting and room purpose, then collect a representative baseline.",
            gate="No qualifying intervention is established for this room in the selected scope.",
            measure="Track reporting coverage, bookings and genuine feedback.",
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
