"""Transparent cost and cash-flow assumptions. Pulse never supplies savings."""
from math import isfinite
import pandas as pd


def _amount(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isfinite(value) or value < 0:
        raise ValueError("Amounts must be blank or finite, non-negative numbers.")
    return float(value)


def annual_costs(property_cost, technology_cost, service_cost):
    values = [_amount(v) for v in [property_cost, technology_cost, service_cost]]
    return sum(values) if all(v is not None for v in values) else None


def cost_allocation(annual_cost, occupied, observed, expected):
    """Budget allocation to the observed pattern, with unknown time retained.

    This is an illustrative allocation, not evidence of avoidable spending.
    """
    cost = _amount(annual_cost)
    if cost is None or expected <= 0:
        return None
    if min(occupied, observed) < 0 or occupied > observed + 1e-8 or observed > expected + 1e-8:
        raise ValueError("Time evidence must reconcile before allocating costs.")
    return {"Occupied": cost * occupied / expected, "Observed empty": cost * (observed-occupied) / expected,
            "Unknown": cost * max(0, expected-observed) / expected}


def business_case(project_cost, annual_savings, annual_extra_cost, years=3):
    project, savings, extra = map(_amount, [project_cost, annual_savings, annual_extra_cost])
    if isinstance(years, bool) or years not in range(1, 11):
        raise ValueError("Choose a horizon from one to ten whole years.")
    if any(v is None for v in [project, savings, extra]):
        return None
    net = savings - extra
    benefit = net * years - project
    payback = project / net * 12 if net > 0 and project > 0 else (0.0 if project == 0 and net > 0 else None)
    return dict(project_cost=project, annual_savings=savings, annual_extra_cost=extra, annual_net=net,
                years=int(years), net_benefit=benefit, roi=100 * benefit / project if project > 0 else None,
                payback_months=payback,
                cashflow=pd.DataFrame({"Year": range(int(years)+1), "Cumulative net cash": [-project + net*t for t in range(int(years)+1)]}))
