"""Versioned, explicitly synthetic survey records and replaceable result calculations.

Only room identities and observation dates seed the demo. Ratings are invented;
they are never inferred from occupancy or environmental measurements.
"""
from hashlib import sha256
import numpy as np
import pandas as pd

AUDIENCES = ["Neat employee", "Customer / guest"]
ISSUES = ["Temperature", "Air quality", "Lighting", "Meeting technology"]
COLUMNS = ["response_id", "schema_version", "timestamp", "clock", "room_key", "location", "room_name",
           "audience", "experience", "equipment", "issue", "comment", "is_demo", "source"]
PRAISE = {
    "Neat employee": ["A comfortable space that makes collaborating with colleagues easy.",
                      "The equipment is simple to use and helps our meetings run smoothly.",
                      "I enjoy working in these spaces; the sound and video feel natural.",
                      "A welcoming room with everything we need for a productive meeting."],
    "Customer / guest": ["Loved the showroom experience. The equipment was so easy to use.",
                         "The picture and sound were excellent. A really impressive demonstration.",
                         "A beautiful space to experience the Neat equipment in action.",
                         "A fantastic visit. The technology made everyone feel part of the conversation."],
}


def demo_record(room, audience, experience, equipment, issue="", comment="", *, timestamp, response_id, source, clock):
    if audience not in AUDIENCES or issue not in ["", *ISSUES]:
        raise ValueError("Choose a valid audience and issue.")
    if any(isinstance(r, bool) or r not in range(1, 6) for r in [experience, equipment]):
        raise ValueError("Both ratings must be between 1 and 5.")
    return dict(response_id=response_id, schema_version=1, timestamp=pd.Timestamp(timestamp), clock=clock,
                room_key=room["Room key"], location=room["Location"], room_name=room["Room Name"], audience=audience,
                experience=int(experience), equipment=int(equipment), issue=issue, comment=comment,
                is_demo=True, source=source)


def sample_feedback(data):
    """Up to four responses per observed weekday/room, stable as new dates arrive.

    One response per recorded office-hours bucket. No records are generated on
    dates without source records, or before/after an individual room's history.
    """
    d = data.loc[data.Capacity.gt(0), ["Timestamp", "Room key", "Location", "Room Name"]].copy()
    d = d[d.Timestamp.dt.dayofweek.lt(5) & d.Timestamp.dt.hour.ge(8) & d.Timestamp.dt.hour.lt(19)]
    d["day"] = d.Timestamp.dt.normalize()
    d["slot"] = ((d.Timestamp.dt.hour - 8) // 3).astype(int)
    anchors = d.sort_values("Timestamp").drop_duplicates(["Room key", "day", "slot"])
    rows = []
    for _, room in anchors.iterrows():
        seed = f"neat-feedback-v1|{room['Room key']}|{room.day.date()}|{room.slot}"
        digest = sha256(seed.encode()).hexdigest()
        rng = np.random.default_rng(int(digest[:16], 16))
        audience = AUDIENCES[int(rng.random() >= .5)]
        guest = audience == AUDIENCES[1]
        experience = int(rng.choice([1, 2, 3, 4, 5], p=[.002, .003, .015, .14, .84] if guest else [.01, .02, .09, .36, .52]))
        equipment = int(rng.choice([1, 2, 3, 4, 5], p=[.001, .002, .007, .1, .89] if guest else [.005, .015, .06, .3, .62]))
        issue = ""
        comment = PRAISE[audience][int(rng.integers(4))]
        if min(experience, equipment) <= 3:
            issue = "Meeting technology" if equipment <= 3 else ISSUES[int(rng.integers(3))]
            comment = {"Temperature": "The room could have been a little more comfortable today.",
                       "Air quality": "A little more fresh air would have helped during our visit.",
                       "Lighting": "The lighting could be adjusted for this meeting.",
                       "Meeting technology": "We needed a little help getting the meeting started."}[issue]
        rows.append(demo_record(room, audience, experience, equipment, issue, comment,
            timestamp=room.Timestamp, response_id="SAMPLE-" + digest[:20], source="Generated sample",
            clock="Recorded source time"))
    out = pd.DataFrame(rows, columns=COLUMNS)
    out["timestamp"] = pd.to_datetime(out.timestamp)
    return out.sort_values("timestamp").reset_index(drop=True)


def filter_feedback(records, room_keys, start, end, office=True, audience="Everyone"):
    mask = records.room_key.isin(room_keys) & records.timestamp.between(start, end)
    if office:
        mask &= records.timestamp.dt.dayofweek.lt(5) & records.timestamp.dt.hour.ge(8) & records.timestamp.dt.hour.lt(19)
    if audience != "Everyone":
        mask &= records.audience.eq(audience)
    return records.loc[mask].copy()


def feedback_summary(records):
    n = len(records)
    return dict(responses=n, positive=100 * records.experience.ge(4).mean() if n else None,
                experience=records.experience.mean() if n else None,
                equipment=records.equipment.mean() if n else None)
