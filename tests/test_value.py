from hashlib import sha256
import pandas as pd
import pytest
from workplace.value import annual_costs, business_case, cost_allocation
from workplace.customer import time_mix, room_story
from workplace.executive import decision_actions
from test_executive import context_fixture
from test_app import app


def test_cashflow_reconciles_upfront_cost_running_cost_roi_and_payback():
    case=business_case(18000,9000,1500,3)
    assert case["annual_net"] == 7500
    assert case["net_benefit"] == 4500
    assert case["roi"] == 25
    assert case["payback_months"] == pytest.approx(28.8)
    assert case["cashflow"]["Cumulative net cash"].tolist()==[-18000,-10500,-3000,4500]
    downside=business_case(18000,4500,1500,3)
    assert downside["net_benefit"]==-9000 and downside["roi"]==-50
    assert downside["payback_months"]==72  # beyond model horizon, not hidden


def test_unknown_and_zero_costs_and_negative_returns_are_distinct():
    assert annual_costs(0,0,None) is None
    assert annual_costs(0,0,0)==0
    assert business_case(100,None,0) is None
    assert business_case(0,100,0)["roi"] is None
    assert business_case(0,100,0)["payback_months"]==0
    assert business_case(100,0,20)["roi"]==-160
    assert business_case(100,0,20)["payback_months"] is None
    for amount in [-1,float("inf"),float("nan"),True]:
        with pytest.raises(ValueError):business_case(amount,100,0)
    with pytest.raises(ValueError):business_case(100,100,0,0)


def test_cost_allocation_never_turns_missing_time_into_empty_time():
    summary=dict(expected_hours=100,valid_hours=70,occupied_hours=20)
    mix=time_mix(summary)
    assert mix.Hours.tolist()==[20,50,30]
    allocated=cost_allocation(10000,20,70,100)
    assert allocated=={"Occupied":2000,"Observed empty":5000,"Unknown":3000}
    assert sum(allocated.values())==10000
    assert cost_allocation(None,20,70,100) is None
    with pytest.raises(ValueError):cost_allocation(100,80,70,100)


def test_room_story_prioritises_missing_evidence_and_actions_cover_distinct_themes():
    ctx=context_fixture()
    row=ctx["stats"].iloc[0].copy()
    row["Coverage %"]=30
    assert "observation gaps" in room_story(row)[0]
    row["Coverage %"]=100
    assert "people or fewer" in room_story(row)[0]
    assert {x["kind"] for x in decision_actions(ctx)}=={"fit","warm","light"}


def test_value_models_remain_scoped_and_scenario_cost_carries_through():
    at=app().switch_page("pages/Scenarios.py").run()
    room=at.selectbox(key="_selected_room").value
    token=sha256(room.encode()).hexdigest()[:12]
    at.number_input(key=f"_scenario_{token}_a_cost_GBP").set_value(21000.).run()
    at.button(key="scenario_value_Option A").click().run()
    at.switch_page("pages/Value.py").run()
    assert not at.exception,[e.message for e in at.exception]
    assert at.number_input(key=f"_value_{token}_GBP_project").value==21000
    assert at.number_input(key=f"_value_{token}_GBP_savings").value is None
    at.button(key="value_example").click().run()
    assert not at.exception,[e.message for e in at.exception]
    assert len(at.get("plotly_chart"))==2
    at.checkbox(key=f"value_representative_{token}_GBP").check().run()
    assert not at.exception
    assert len(at.get("plotly_chart"))==3
    at.selectbox(key="_value_currency").select("EUR").run()
    assert at.number_input(key=f"_value_{token}_EUR_project").value is None
    at.selectbox(key="_value_currency").select("GBP").run()
    assert at.number_input(key=f"_value_{token}_GBP_project").value==18000
    at.selectbox(key="_preset").select("Last 30 days").run()
    assert not at.exception
    assert at.number_input(key=f"_value_{token}_GBP_project").value==18000
