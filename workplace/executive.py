"""Decision briefs grounded in existing observations, without inferred ROI."""
from __future__ import annotations

import pandas as pd


MIN_REVIEW_COVERAGE = 70


def evidence_summary(ctx):
    summary, stats = ctx["summary"], ctx["stats"]
    coverage = summary["coverage"]
    ready = stats["Coverage %"].ge(MIN_REVIEW_COVERAGE)
    if pd.isna(coverage) or summary["valid_hours"] <= 0:
        label, tone = "No valid occupancy evidence", "limited"
    elif coverage < MIN_REVIEW_COVERAGE:
        label, tone = "Limited observation coverage", "limited"
    else:
        label, tone = "Coverage supports investigation", "review"
    if ctx.get("demo", False):
        label, tone = "Demonstration data", "demo"
    return dict(label=label, tone=tone, coverage=coverage,
                rooms_ready=int(ready.sum()), rooms_total=len(stats),
                latest=ctx.get("latest_source", ctx["inventory"].Timestamp.max()),
                status_unreported=ctx.get("quality", {}).get("status_unreported", False))


def decision_actions(ctx, limit=3):
    """Data readiness first, then distinct rooms across decision themes.

    70% is an explicit review-screening rule, not a confidence score or an
    investment approval. Low-coverage room findings remain available in Insights.
    """
    quality = evidence_summary(ctx)
    stats = ctx["stats"].set_index("Room key")
    actions = []
    low = quality["rooms_total"] - quality["rooms_ready"]
    if low:
        actions.append(dict(kind="coverage", room_key=None, scope="Selected rooms",
            title="Strengthen the evidence before investing",
            evidence=f"{low} of {quality['rooms_total']} rooms have less than 70% occupancy coverage.",
            action="Check reporting gaps and device status, then collect a representative period.",
            benefit="Make room decisions from observed demand rather than missing readings.",
            owner="IT + Workplace", cost="Not assessed", coverage=None,
            measure="Review per-room coverage and peak-day representation before a pilot."))
    templates = {
        "fit": ("Validate the mix of room sizes",
                "Make suitable spaces easier to find for different group sizes.",
                "Check peak demand, bookings, room purpose and accessibility before a redesign.",
                "Compare suitable-room availability and employee feedback after a pilot."),
        "warm": ("Review empty-room temperature",
                 "Keep rooms comfortable while checking unnecessary heating or cooling.",
                 "Check HVAC state, upcoming bookings and occupied-room comfort with Facilities.",
                 "Check occupied comfort and meter readings before and after any approved change."),
        "light": ("Review empty-room lighting",
                  "Keep spaces welcoming while checking avoidable lighting operation.",
                  "Check actual lighting, daylight, bookings and safety needs with Facilities.",
                  "Compare lighting operation and metered energy after an approved trial."),
    }
    seen = set()
    ranked = ctx["issues"].copy()
    # Cover different customer decisions before showing another finding of the same kind.
    ranked["theme_order"] = ranked.Kind.map({"fit":0,"warm":1,"light":2}).fillna(3)
    ranked = ranked.sort_values(["theme_order","Evidence hours","Room key"],ascending=[True,False,True])
    eligible = ranked[ranked["Room key"].map(stats["Coverage %"]).ge(MIN_REVIEW_COVERAGE)]
    first_indices, chosen_rooms = [], set()
    for kind in ["fit","warm","light"]:
        theme = eligible[eligible.Kind.eq(kind) & ~eligible["Room key"].isin(chosen_rooms)]
        if not theme.empty:
            first_indices.append(theme.index[0])
            chosen_rooms.add(theme.iloc[0]["Room key"])
    ranked = pd.concat([eligible.loc[first_indices],eligible.drop(first_indices)])
    for _, row in ranked.iterrows():
        key = row["Room key"]
        if key in seen or key not in stats.index or row.Kind not in templates:
            continue
        coverage = stats.loc[key, "Coverage %"]
        if pd.isna(coverage) or coverage < MIN_REVIEW_COVERAGE:
            continue
        seen.add(key)
        title, benefit, action, measure = templates[row.Kind]
        actions.append(dict(kind=row.Kind, room_key=key, scope=key, title=title,
                            evidence=row.Evidence, action=action, benefit=benefit,
                            owner=row.Owner, cost="Not assessed", coverage=float(coverage), measure=measure))
        if len(actions) >= limit:
            break
    if not actions:
        actions.append(dict(kind="baseline", room_key=None, scope="Selected rooms",
            title="Establish a representative baseline",
            evidence="No findings meet the selected investigation thresholds.",
            action="Review a longer period and peak days; validate room purpose with employees.",
            benefit="Identify useful improvements without assuming that no flags means no problems.",
            owner="Workplace", cost="Not assessed", coverage=None,
            measure="Agree an employee outcome and baseline before selecting an investment."))
    return actions[:limit]
