import json
from pathlib import Path

from streamlit.testing.v1 import AppTest
from workplace.briefing import action_signal, simulation_config
from test_executive import context_fixture


def presentation():
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=60)
    at.session_state["demo_mode"] = True
    return at.run()


def test_four_chapters_keep_scope_and_can_return_to_the_full_dashboard():
    at = presentation()
    assert not at.exception
    assert at.toggle(key="_presentation_mode").value is True
    at.selectbox(key="_preset").select("Last 30 days").run()
    for page in ["pages/Spaces.py", "pages/Feedback.py", "pages/Environment.py"]:
        at.switch_page(page).run()
        assert not at.exception, [e.message for e in at.exception]
        assert at.selectbox(key="_preset").value == "Last 30 days"
        assert at.toggle(key="_presentation_mode").value is True
    at.toggle(key="_presentation_mode").set_value(False).run()
    assert not at.exception
    assert at.button(key="environment_run")
    assert at.selectbox(key="_preset").value == "Last 30 days"


def test_finance_stays_opt_in_and_separate_from_control_simulation():
    at = presentation().switch_page("pages/Environment.py").run()
    assert not at.exception
    assert at.toggle(key="_overview_example").value is False
    at.button(key="brief_show_savings").click().run()
    assert not at.exception
    assert at.toggle(key="_overview_example").value is True
    html = " ".join(e.proto.body for e in at.get("html"))
    assert "£7,500" in html and "ILLUSTRATIVE" in html
    at.button(key="brief_run").click().run()
    assert not at.exception
    run = at.session_state["brief_workflow"]
    assert run["payload"]["mode"] == "simulation"
    assert run["payload"]["command_sent"] is False
    assert run["payload"]["service_now_ticket_id"] is None
    assert run["payload"]["gateway_acknowledgement"] is None
    assert run["payload"]["measured_saving"] is None
    at.selectbox(key="_brief_condition").select("light").run()
    assert not at.exception
    assert not any("Simulation replayed" in e.proto.body for e in at.get("html"))


def test_low_coverage_cannot_authorise_a_presentation_control_demo():
    ctx = context_fixture()
    room = "London EC / Barra"
    assert action_signal(ctx, room, "warm") is not None
    ctx["stats"].loc[ctx["stats"]["Room key"].eq(room), "Coverage %"] = 60
    assert action_signal(ctx, room, "warm") is None
    ctx["thresholds"] = {"warm": 22, "bright": 50, "minimum": 1}
    config = simulation_config(ctx, room, "warm", None)
    assert json.loads(json.dumps(config))["command_sent"] is False


def test_feedback_audience_and_survey_dialog_remain_usable():
    at = presentation().switch_page("pages/Feedback.py").run()
    at.get("button_group")[0].set_value("Customer / guest").run()
    assert not at.exception
    assert at.session_state["feedback_audience"] == "Customer / guest"
    at.button(key="brief_try_survey").click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert any(b.label == "Share feedback" for b in at.button)
    next(b for b in at.button if b.label == "Share feedback").click().run()
    assert not at.exception
    assert any("rate both" in w.value for w in at.warning)
    assert "feedback_tryouts" not in at.session_state
