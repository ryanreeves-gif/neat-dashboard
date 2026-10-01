from hashlib import sha256
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from workplace import ui as u, customer as c, visuals as v, analytics as a
from workplace.scenarios import room_evidence
from workplace.value import annual_costs, business_case, cost_allocation
from workplace.views import choose_room, csv_download


def load_example(token):
    for name, value in {"property":60000.,"technology":4500.,"service":3000.,"project":18000.,"savings":9000.,"extra":1500.}.items():
        st.session_state[f"value_{token}_{name}"] = value
    st.session_state[f"value_{token}_example"] = True


def money_input(label, token, name):
    return st.number_input(label, min_value=0., step=500., value=None, placeholder="Not assessed",
                           **u.field_state(f"value_{token}_{name}", None))


def money(value, currency):
    return "Not assessed" if value is None else f"{'-' if value < 0 else ''}{ {'GBP':'£','EUR':'€','NOK':'kr '}[currency]}{abs(value):,.0f}"


def value_page():
    u.shell("Value & ROI", "Make the investment case.", "Understand room costs, test a proposed change and see what must be true for it to pay back.")
    v.styles()
    ctx = u.context()
    room = choose_room(ctx, "Room for the business case")
    selected = ctx["stats"].set_index("Room key").loc[room]
    currency = st.selectbox("Model currency", ["GBP", "EUR", "NOK"], **u.field_state("value_currency", "GBP"))
    token = sha256(room.encode()).hexdigest()[:12] + "_" + currency
    c.answer("The question to answer", "What would make this change worth funding?",
             "Pulse shows how this room is used. Add cost and savings assumptions to test a business case, then validate them in a pilot.",
             "sunrise", u.fmt(selected["Utilisation %"], "%"), "observed time in use")
    st.button("Load an illustrative example", key="value_example", on_click=load_example, args=(token,))
    if st.session_state.get(f"value_{token}_example", False):
        st.info("Illustrative cost assumptions loaded. Edit them for your demonstration; these are not Neat prices or measured customer savings.")
    st.caption(f"Assumptions belong to {room}, in {currency}. Currency changes select a separate model; no exchange-rate conversion is performed.")
    cost_tab, case_tab = st.tabs(["1 · Understand the current cost", "2 · Test a proposed investment"])
    with cost_tab:
        left, right = st.columns([1, 1.1], gap="large")
        with left:
            st.subheader("Annual running costs")
            st.caption("Enter each category once. Use zero where there is no cost; blank stays unknown.")
            property_cost = money_input(f"Space / property allocation ({currency} per year)", token, "property")
            technology = money_input(f"Equipment + licences ({currency} per year)", token, "technology")
            service = money_input(f"Facilities + support ({currency} per year)", token, "service")
            st.caption("Use consistent annual costs, for example annualised equipment cost rather than the full purchase price. Keep energy and support in one category only.")
        annual = annual_costs(property_cost, technology, service)
        with right, st.container(key="panel_annual_cost"):
            c.stat("Annual cost entered", money(annual, currency), "Room-specific planning assumption", "sunrise", "Entered assumptions")
            if annual is None:
                st.info("Complete all three categories to show the cost profile, or load the labelled example.")
            elif annual > 0:
                fig=go.Figure(go.Pie(labels=["Space / property","Equipment + licences","Facilities + support"], values=[property_cost,technology,service],hole=.7,
                    marker=dict(colors=["#93ABB3","#5F259F","#DBC684"]),sort=False,textinfo="percent",
                    hovertemplate=f"%{{label}}<br>{currency} %{{value:,.0f}} / year<extra></extra>"))
                u.plot_style(fig,290)
                fig.update_layout(legend=dict(orientation="h",y=-.12,x=0),margin=dict(t=10,b=20))
                st.plotly_chart(fig,width="stretch",config={"displayModeBar":False},key="value_cost_profile")
            else:
                st.caption("Zero annual cost entered in every category.")
        with st.expander("Map that budget to the observed room pattern"):
            st.caption("Illustration only: assumes this selected period represents the annual pattern. Empty-room budget is allocated cost, not automatically recoverable savings.")
            accepted = st.checkbox("Use this period as an illustrative annual pattern", key="value_representative_"+token)
            evidence=room_evidence(ctx["samples"],room,a.window_hours(ctx["start"],ctx["end"],ctx["office"]))
            if accepted and annual is not None:
                allocation=cost_allocation(annual,evidence["occupied_hours"],evidence["observed_hours"],evidence["expected_hours"])
                if allocation:
                    fig=go.Figure()
                    for label,colour in zip(allocation,["#638C7D","#93ABB3","#DBC684"]):
                        fig.add_trace(go.Bar(name=label,x=[allocation[label]],y=["Annual budget"],orientation="h",marker_color=colour,
                            hovertemplate=f"{label}<br>{currency} %{{x:,.0f}} allocated<extra></extra>"))
                    u.plot_style(fig,170)
                    fig.update_layout(barmode="stack",legend=dict(orientation="h",y=1.3),margin=dict(t=35))
                    fig.update_xaxes(title=f"{currency} · allocation, not savings")
                    st.plotly_chart(fig,width="stretch",config={"displayModeBar":False},key="value_allocation")
                    st.dataframe(pd.DataFrame({"Observed state":allocation.keys(),f"Allocated {currency}":allocation.values()}).round(0),hide_index=True,width="stretch")
                if evidence["coverage"] is None or evidence["coverage"]<70:
                    st.warning("Limited observation coverage: the annual pattern is particularly uncertain. Unknown time retains its share of the budget.")
        c.next_step("Validate the largest cost category and busiest periods before deciding what can actually be reduced.")
    with case_tab:
        left,right=st.columns([1,1.7],gap="large")
        with left:
            st.subheader("A proposed change")
            project=money_input(f"One-off project cost ({currency})",token,"project")
            savings=money_input(f"Expected annual cash savings ({currency})",token,"savings")
            extra=money_input(f"Additional annual running cost ({currency})",token,"extra")
            years=st.selectbox("Assessment period (years)",[1,2,3,4,5,7,10],**u.field_state(f"value_{token}_years",3))
            st.caption("Savings need an independent estimate. Do not convert empty time or sample satisfaction into cash automatically.")
            st.page_link("pages/Scenarios.py",label="Check the room layout first",icon=":material/compare_arrows:")
        result=business_case(project,savings,extra,years)
        with right,st.container(key="panel_cashflow"):
            st.html('<span class="source-tag assumption">Projected outcome · entered assumptions</span>')
            if result is None:
                st.subheader("No return claimed until the assumptions are entered.")
                st.write("Add project cost, annual cash savings and additional annual running cost to see cumulative cash flow and payback.")
            else:
                for column,(label,val,detail,tone) in zip(st.columns(3),[
                    (f"{years}-year net benefit",money(result["net_benefit"],currency),"After project and extra running costs","forest"),
                    (f"{years}-year ROI",u.fmt(result["roi"],"%",1) if result["roi"] is not None else "N/A","Net benefit / initial project cost","purple"),
                    ("Simple payback",f"{result['payback_months']:.0f} months" if result["payback_months"] is not None else "No payback","Assumes savings accrue evenly","sunrise")]):
                    with column:c.stat(label,val,detail,tone)
                fig=go.Figure()
                for factor,label,colour in [(0.5,"50% of expected savings","#9F8884"),(1.,"Entered case","#5F259F"),(1.25,"125% of expected savings","#638C7D")]:
                    case=business_case(project,savings*factor,extra,years)
                    fig.add_trace(go.Scatter(x=case["cashflow"].Year,y=case["cashflow"]["Cumulative net cash"],mode="lines+markers",name=label,
                        line=dict(color=colour,width=3 if factor==1 else 2,dash="solid" if factor==1 else "dot"),
                        hovertemplate=f"Year %{{x}}<br>{currency} %{{y:,.0f}} cumulative<extra>%{{fullData.name}}</extra>"))
                u.plot_style(fig,320)
                fig.add_hline(y=0,line_color="#4C515C",line_width=1)
                fig.update_layout(legend=dict(orientation="h",y=1.25),margin=dict(t=55))
                fig.update_yaxes(title=f"Cumulative net cash ({currency})")
                fig.update_xaxes(title="Years from investment",dtick=1)
                st.plotly_chart(fig,width="stretch",config={"displayModeBar":False},key="value_cashflow")
                if result["payback_months"] is not None and result["payback_months"]>years*12:
                    st.caption("Payback falls beyond the selected assessment period.")
                st.caption("Sensitivity cases change savings only. No discounting, tax, inflation, residual value or staged savings is included.")
        c.next_step("Agree a baseline, owner and review date. Check actual costs, usage and real feedback after a pilot.")
    export={"Room":room,"Currency":currency,"Period start":ctx["start"],"Period end":ctx["end"],"Operating hours":"Office hours" if ctx["office"] else "All hours",
            "Coverage %":selected["Coverage %"],"Time in use %":selected["Utilisation %"],"Annual property cost":property_cost,"Annual technology cost":technology,
            "Annual facilities/support cost":service,"Annual total":annual,"Project cost":project,"Expected annual savings":savings,"Additional annual cost":extra,
            "Years":years,"Projected net benefit":result["net_benefit"] if result else None,"Projected ROI %":result["roi"] if result else None,
            "Payback months":result["payback_months"] if result else None,"Cost source":"Entered assumptions; not measured financial outcomes",
            "Illustrative preset loaded":st.session_state.get(f"value_{token}_example",False),"Telemetry source":"Generated demo" if ctx["demo"] else "Pulse feed",
            "Method":"Simple undiscounted cash flow; savings independent of telemetry and sample sentiment. No tax, inflation, residual value or staged savings."}
    csv_download(pd.DataFrame([export]),"Download the business-case assumptions","neat-business-case-ASSUMPTIONS.csv","value_export")
    u.footer()
