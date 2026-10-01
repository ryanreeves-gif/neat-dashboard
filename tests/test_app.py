from streamlit.testing.v1 import AppTest
from pathlib import Path


def app():
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=45)
    at.session_state["demo_mode"] = True
    at.session_state["presentation_mode"] = False
    return at.run()


def test_all_pages_and_shared_filters():
    at = app()
    assert not at.exception
    assert at.get("popover")
    at.selectbox(key="_preset").select("Last 30 days").run()
    at.selectbox(key="_hours").select("All hours").run()
    for page in ["pages/Spaces.py", "pages/Feedback.py", "pages/Scenarios.py", "pages/Value.py", "pages/Environment.py", "pages/Insights.py", "pages/Administration.py", "pages/AI_Search.py"]:
        at.switch_page(page).run()
        assert not at.exception, [e.message for e in at.exception]
        assert at.selectbox(key="_preset").value == "Last 30 days"
        assert at.selectbox(key="_hours").value == "All hours"
        assert at.session_state["demo_mode"] is True
        assert any("Demonstration mode" in e.value for e in at.info)


def test_empty_location_has_useful_state():
    at = app()
    at.multiselect(key="_locations").set_value([]).run()
    assert not at.exception
    assert any("Select at least one location" in e.value for e in at.info)


def test_custom_dates_and_room_navigation():
    at = app()
    at.selectbox(key="_preset").select("Custom dates").run()
    assert not at.exception
    assert len(at.date_input) == 1
    at.button(key="fit_room").click().run()
    # AppTest records the page switch; render the destination to check preserved selection.
    selected = at.session_state["selected_room"]
    at.switch_page("pages/Spaces.py").run()
    assert not at.exception
    assert at.selectbox(key="_selected_room").value == selected
