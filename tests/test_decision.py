import math
import pandas as pd
import pytest
from workplace.office_opportunity import opportunities, office_scenario, programme_costs
from test_executive import context_fixture
from test_briefing import presentation


def office():
    ctx = context_fixture()
    ctx['stats'].loc[ctx['stats']['Room Name'].eq('Barra'), 'Capacity'] = 20
    return ctx


def assumptions():
    return dict(gross=1200, running=150, control_project=1800, split_project=12000,
                extra_running=250, illustrative=True)


def test_office_totals_count_projects_once_and_protect_largest_room():
    ctx = office()
    # Two signals on the same room must never create two savings projects.
    issue = ctx['issues'][ctx['issues']['Room key'].eq('London EC / Barra')].iloc[[0]].copy()
    issue['Kind'] = 'light'
    ctx['issues'] = pd.concat([ctx['issues'], issue], ignore_index=True)
    model = office_scenario(ctx, ['London EC / Arran'] * 2 + ['London EC / Barra', 'Other / Room'], assumptions=assumptions())
    assert model['controls'] == ['London EC / Barra', 'London EC / Harris']
    assert model['protected'] == ['London EC / Barra']
    assert (model['before_count'], model['after_count'], model['additional']) == (3, 4, 1)
    assert model['before_mix'] == [0, 0, 2, 1]
    assert model['after_mix'] == [0, 2, 1, 1]
    assert model['splits'][0]['after'] == [6, 6]
    assert model['fit'] == 100
    assert model['costs']['annual_net'] == 1850
    assert model['costs']['project_cost'] == 15600
    assert model['costs']['illustrative'] is True


def test_replay_never_splits_a_group_across_two_rooms_or_counts_empty_time():
    ctx = office()
    first = ctx['samples'].index[ctx['samples']['Room key'].eq('London EC / Arran')][0]
    ctx['samples'].loc[first, 'Occupancy'] = 7
    m = office_scenario(ctx, ['London EC / Arran'])
    assert m['occupied'] == pytest.approx(11)
    assert m['exceeds'] == pytest.approx(1/6)
    assert m['fit'] == pytest.approx(100 * (11 - 1/6) / 11)
    assert m['costs'] is None
    assert m['splits'][0]['peak'] == 7
    with pytest.raises(ValueError):
        office_scenario(ctx, ['London EC / Arran'], {'London EC / Arran': 12})


def test_room_filters_low_coverage_and_display_assets_do_not_inflate_totals():
    ctx = office()
    ctx['stats'].loc[ctx['stats']['Room Name'].eq('Arran'), 'Coverage %'] = 60
    asset = ctx['stats'].iloc[[0]].copy()
    asset['Room key'] = "London EC / Shelf o' Frames"
    asset['Room Name'] = "Shelf o' Frames"
    ctx['stats'] = pd.concat([ctx['stats'], asset])
    m = office_scenario(ctx, ['London EC / Arran'])
    assert m['additional'] == 0 and m['before_count'] == 3 and len(m['ready']) == 2
    assert m['fit'] is None  # remaining rooms were empty; missing evidence isn't perfect fit
    ctx['stats'] = ctx['stats'][ctx['stats']['Room Name'].eq('Harris')]
    m = office_scenario(ctx, ['London EC / Arran'], assumptions=assumptions())
    assert m['controls'] == ['London EC / Harris']
    assert m['before_count'] == 1 and m['additional'] == 0
    assert m['costs']['annual_net'] == 1050


def test_costs_keep_negative_benefit_and_no_evidence_has_no_cost_case():
    assert programme_costs(0, 0, assumptions()) is None
    result = programme_costs(0, 2, assumptions())
    assert result['annual_net'] == -500 and result['payback_months'] is None
    with pytest.raises(ValueError):
        programme_costs(1, 1, {**assumptions(), 'gross': math.nan})
    ctx = office()
    ctx['stats']['Coverage %'] = 0
    model = office_scenario(ctx, ['London EC / Arran'], assumptions=assumptions())
    assert model['additional'] == 0 and model['costs'] is None and model['fit'] is None


def test_office_page_aggregates_without_changing_exploration_room_or_adding_main_controls():
    at = presentation().switch_page('pages/Environment.py').run()
    room = at.session_state['selected_room']
    at.switch_page('pages/Next_Steps.py').run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.session_state['selected_room'] == room
    assert not at.main.button and not at.main.get('button_group') and not at.get('iframe')
    assert len(at.main.selectbox) == 2
    markup = ' '.join(e.proto.body for e in at.get('html'))
    for text in ['More value from the whole office', 'Concept additional rooms', 'Observed group fit',
                 'A different room mix', 'One office programme', 'physical fit unverified', 'Illustrative annual net benefit']:
        assert text in markup
    at.selectbox(key='_office_cost_mode').set_value('Not costed').run()
    markup = ' '.join(e.proto.body for e in at.get('html'))
    assert 'Not costed' in markup and '£' not in markup
    at.selectbox(key='_office_cost_mode').set_value('Entered estimates').run()
    assert at.number_input(key='_office_entered_gross').value == 0
    at.main.multiselect(key='_room_filter').set_value([room]).run()
    assert not at.exception
    markup = ' '.join(e.proto.body for e in at.get('html'))
    assert '1 today → 1 in concept' in markup
    at.toggle(key='_presentation_mode').set_value(False).run()
    assert not at.exception
