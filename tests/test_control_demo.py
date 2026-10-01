import json
import math

import pytest
from workplace.control_demo import animation_html, preview_state, scenario
from test_briefing import presentation


def test_lighting_and_ventilation_restore_without_claiming_real_outcomes():
    lights = scenario('light', 15, brightness=0)
    assert preview_state(lights, 0)['light'] == 80
    assert preview_state(lights, 5)['light'] == 0
    assert preview_state(lights, 15)['light'] == 80
    assert preview_state(lights, 16)['expired'] is True
    air = scenario('purge', 20, boost=100)
    active = preview_state(air, 10)
    expired = preview_state(air, 20)
    assert active['fan'] == 100 and expired['fan'] == 30
    assert 0 < expired['air_indicator'] < active['air_indicator'] < 100
    assert air['command_sent'] is False and air['measured_saving'] is None
    assert 'Invented' in air['basis']


def test_ac_distinguishes_setpoint_from_room_temperature_and_does_not_reverse_conditions_at_expiry():
    ac = scenario('warm', 15, temperature=20, start_temperature=26)
    active = preview_state(ac, 14.9)
    expired = preview_state(ac, 15)
    assert active['setpoint'] == 20
    assert 20 < active['room_temperature'] < 26
    assert expired['setpoint'] == 24
    assert abs(expired['room_temperature'] - active['room_temperature']) < .2
    heat = scenario('warm', 15, temperature=28, start_temperature=22)
    assert preview_state(heat, 10)['room_temperature'] > 22
    for args in [('bad', 15), ('light', 0), ('purge', math.nan)]:
        with pytest.raises(ValueError):
            scenario(*args)
    with pytest.raises(ValueError):
        scenario('light', 15, brightness=101)


def test_iframe_configuration_is_safe_data_and_only_runs_when_requested():
    markup = animation_html(scenario('purge', 15), '</script><script>alert(1)</script>')
    raw = markup.split('<script type="application/json" id="config">')[1].split('</script>')[0]
    parsed = json.loads(raw)
    assert parsed['running'] is False and len(parsed['frames']) == 121
    assert '</script>' not in raw
    assert parsed['room_name'] == '</script><script>alert(1)</script>'
    assert '__CONFIG__' not in markup and '__FONT__' not in markup and '__BOLD_FONT__' not in markup


def test_all_three_controls_capture_settings_invalidate_changes_and_reset():
    at = presentation().switch_page('pages/Environment.py').run()
    assert not at.exception, [e.message for e in at.exception]
    for kind, key, value in [('warm', '_brief_ac_target', 20.0),
                             ('light', '_brief_light_target', 0),
                             ('purge', '_brief_air_boost', 100)]:
        at.selectbox(key='_brief_condition').select(kind).run()
        at.slider(key=key).set_value(value).run()
        at.slider(key='_brief_control_minutes').set_value(20).run()
        at.button(key='brief_run').click().run()
        assert not at.exception, [e.message for e in at.exception]
        settings = at.session_state['brief_workflow']['payload']['settings']
        assert settings['kind'] == kind and settings['duration'] == 20
        assert settings[{'warm':'temperature','light':'brightness','purge':'boost'}[kind]] == value
        assert settings['command_sent'] is False
        assert at.get('iframe')
        at.slider(key='_brief_control_minutes').set_value(25).run()
        assert 'brief_workflow' not in at.session_state
    at.button(key='brief_run').click().run()
    at.button(key='brief_reset').click().run()
    assert 'brief_workflow' not in at.session_state
    at.button(key='brief_run').click().run()
    options = at.selectbox(key='_selected_room').options
    at.selectbox(key='_selected_room').select(options[-1]).run()
    assert 'brief_workflow' not in at.session_state
    assert not at.exception
