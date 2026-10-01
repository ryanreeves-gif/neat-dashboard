import pandas as pd
import pytest

from workplace import portfolio as p
from test_executive import context_fixture


def feedback():
    return pd.DataFrame([
        {"room_key": "London EC / " + room, "experience": score, "equipment": 5}
        for room, scores in [("Arran", [4] * 5), ("Barra", [5] * 5), ("Harris", [5] * 4)]
        for score in scores
    ])


def test_usage_and_sentiment_have_independent_winners_and_evidence_rules():
    ctx = context_fixture()
    rooms = p.room_portfolio(ctx, feedback())
    assert p.room_leaders(rooms, "usage")["Room Name"].tolist() == ["Arran"]
    assert p.room_leaders(rooms, "sentiment")["Room Name"].tolist() == ["Barra"]
    assert set(p.comparison_rows(rooms)["Room Name"]) == {"Arran", "Barra"}
    # Missing telemetry cannot silently become a room recommendation; sentiment
    # remains independently visible when there are sufficient survey responses.
    ctx["stats"].loc[ctx["stats"]["Room Name"].eq("Barra"), "Coverage %"] = 60
    rooms = p.room_portfolio(ctx, feedback())
    assert p.room_leaders(rooms, "sentiment")["Room Name"].tolist() == ["Barra"]
    assert set(p.comparison_rows(rooms)["Room Name"]) == {"Arran"}
    assert "Barra" not in p.opportunity_rows(rooms)["Room Name"].tolist()


def test_both_routes_survive_and_synthetic_ratings_cannot_change_them():
    ctx = context_fixture()
    extra = ctx["issues"].query("Kind == 'warm'").iloc[0].copy()
    extra["Room key"], extra["Room"] = "London EC / Arran", "Arran"
    ctx["issues"] = pd.concat([ctx["issues"], extra.to_frame().T], ignore_index=True)
    rooms = p.room_portfolio(ctx, feedback())
    assert rooms.set_index("Room Name").loc["Arran", "Route"] == "Controls + layout"
    changed = feedback().assign(experience=1, equipment=1)
    other = p.room_portfolio(ctx, changed)
    pd.testing.assert_series_equal(rooms.Route, other.Route)
    assert p.opportunity_rows(rooms)["Room Name"].tolist()[0] == "Arran"
    fig = p.opportunity_figure(rooms, "Arial")
    assert list(fig.data[0].z[0]) == [1, 1]


def test_ties_and_empty_feedback_are_explicit_and_graph_data_matches_scope():
    ctx = context_fixture()
    records = feedback()
    records.loc[records.room_key.str.endswith("Arran"), "experience"] = 5
    rooms = p.room_portfolio(ctx, records)
    assert p.room_leaders(rooms, "sentiment")["Room Name"].tolist() == ["Arran", "Barra"]
    fig = p.performance_figure(rooms, ctx["summary"]["utilisation"], "Arial")
    assert set(fig.layout.meta["rooms"]) == {"London EC / Arran", "London EC / Barra"}
    assert fig.layout.meta["sentiment_is_synthetic"] is True
    empty = p.room_portfolio(ctx, records.iloc[:0])
    assert p.room_leaders(empty, "sentiment").empty
    assert p.comparison_rows(empty).empty
    assert p.room_leaders(empty, "usage")["Room Name"].tolist() == ["Arran"]
    with pytest.raises(ValueError):
        p.room_leaders(rooms, "combined")
