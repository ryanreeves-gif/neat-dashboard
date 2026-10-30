from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from workplace.health import latest_signin, replay_events, make_demo, current_demo
from test_executive import context_fixture


def test_signout_requires_explicit_later_recovery_and_respects_event_time_and_room():
    start, end = pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-02")
    events = replay_events("Teams room", start, end, 2)
    assert latest_signin([], "Teams room", end) == "Unknown"
    assert latest_signin(events, "another room", end) == "Unknown"
    assert latest_signin(events, "Teams room", start) == "Unknown"
    assert latest_signin(events, "Teams room", pd.Timestamp(events[1]["occurred_at"])) == "Signed out"
    assert latest_signin([events[1], events[0], events[1]], "Teams room", end) == "Signed out"
    assert latest_signin(list(reversed(events)) + [events[0]], "Teams room", end) == "Signed in"


def test_demo_never_changes_device_observations_and_invalidates_after_scope_changes():
    ctx = context_fixture()
    room = "London EC / Barra"
    ctx["inventory"].loc[ctx["inventory"]["Room key"].eq(room), "Platform"] = "Microsoft Teams"
    before = ctx["inventory"].copy(deep=True)
    saved = make_demo(ctx, room, 1)
    session = {"health_demo": saved}
    assert saved["status"] == "Signed out"
    assert saved["command_sent"] is False and saved["ticket_created"] is False
    assert current_demo(ctx, session) == saved
    pd.testing.assert_frame_equal(before, ctx["inventory"])
    changed = deepcopy(ctx)
    changed["end"] += pd.Timedelta(hours=1)
    assert current_demo(changed, session) is None
    changed = deepcopy(ctx)
    changed["office"] = False
    assert current_demo(changed, session) is None
    changed = deepcopy(ctx)
    changed["inventory"] = changed["inventory"][changed["inventory"]["Room key"].ne(room)]
    assert current_demo(changed, session) is None
    with pytest.raises(ValueError):
        make_demo(ctx, "London EC / Arran", 1)  # not recorded as Teams


def app():
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=60)
    at.session_state["demo_mode"] = True
    return at.run()


def test_alert_recovery_and_recommendation_follow_the_same_scoped_example():
    at = app()
    assert not at.exception, [e.message for e in at.exception]
    room = at.selectbox(key="_health_demo_room").value
    assert at.session_state["health_demo"]["stage"] == 0
    assert len(at.main.button) == 1
    at.button(key="health_advance").click().run()
    assert not at.exception
    assert at.session_state["health_demo"]["status"] == "Signed out"
    at.switch_page("pages/Improve.py").run()
    assert not at.exception, [e.message for e in at.exception]
    html = " ".join(e.proto.body for e in at.get("html"))
    assert "Restore Teams sign-in" in html and room.split(" / ")[-1] in html
    at.switch_page("app.py").run()
    at.button(key="health_advance").click().run()
    assert not at.exception
    assert at.session_state["health_demo"]["status"] == "Signed in"
    assert at.session_state["health_demo"]["stage"] == 2
    at.switch_page("pages/Improve.py").run()
    assert any("Verify the room after recovery" in e.proto.body for e in at.get("html"))
    # Changing the common date scope invalidates the earlier replay on every page.
    at.selectbox(key="_preset").select("Last 30 days").run()
    assert "health_demo" not in at.session_state
    assert not any("Verify the room after recovery" in e.proto.body for e in at.get("html"))


def test_non_teams_scope_cannot_show_an_invented_microsoft_signin():
    at = app()
    teams_room = at.selectbox(key="_health_demo_room").value
    # Demo-data rooms alternate platforms; use the room map's recorded metadata.
    from workplace.analytics import demo_data, prepare, inventory
    inv = inventory(prepare(demo_data())[0])
    non_teams = inv.loc[inv.Platform.eq("Zoom"), "Room key"].iloc[0]
    assert non_teams != teams_room
    at.multiselect(key="_room_filter").set_value([non_teams]).run()
    assert not at.exception
    assert "health_demo" not in at.session_state
    assert not any(b.key == "health_advance" for b in at.main.button)
    assert any("No Microsoft Teams room" in message.value for message in at.info)


def test_environment_opens_with_three_trends_and_no_extra_navigation_controls():
    at = app().switch_page("pages/Environment.py").run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.get("plotly_chart")) == 1
    assert not at.main.button
    assert not at.main.get("button_group")
    assert any("not CO₂" in item.proto.body for item in at.get("html"))
