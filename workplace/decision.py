"""One-screen office opportunity, with scenario inputs in presenter tools."""
from hashlib import sha256
from html import escape
import streamlit as st
from workplace import ui as u, office_map
from workplace.office_opportunity import opportunities, office_scenario
from workplace.overview_view import money


def scenario_inputs(ctx):
    base = opportunities(ctx)
    key = "office_splits_" + base["token"]
    options = base["candidates"]["Room key"].tolist()
    st.session_state[key] = [r for r in st.session_state.get(key, options[:2]) if r in options]
    with ctx["tools"].expander("Office layout scenario"):
        st.caption("Concept only. The picture has no measured dimensions. Splitting a room needs a space, access, acoustics, ventilation and AV review.")
        chosen = st.multiselect("Rooms to explore splitting", options, **u.field_state(key, options[:2]))
        seats = {}
        capacities = base["rooms"].set_index("Room key").Capacity
        for room in chosen:
            token = sha256(room.encode()).hexdigest()[:12]
            capacity = int(capacities[room])
            default = min(capacity - 1, max(1, int(st.session_state.get("brief_seats_" + token, capacity // 2))))
            input_key = "office_first_" + token
            st.session_state[input_key] = min(capacity - 1, max(1, int(st.session_state.get(input_key, default))))
            seats[room] = st.number_input(f'{room.split(" / ")[-1]} · first room seats', 1, capacity - 1,
                                         **u.field_state(input_key, default))
            st.caption(f"Second room: {capacity - seats[room]} seats. Seat count is held constant; physical fit is unverified.")
        st.caption("At least one of the largest rooms in each selected office is retained. Only layout candidates with ≥70% coverage, ≥2 observed hours and ≥2 occupied hours are offered.")
        st.caption("The initial concept tests up to two candidates, ordered by capacity. It is not an architectural recommendation. Clear the Rooms filter above to review the whole selected office.")
    with ctx["tools"].expander("Office programme costs · GBP"):
        mode = st.selectbox("Cost basis", ["Illustrative example", "Entered estimates", "Not costed"],
                            **u.field_state("office_cost_mode", "Illustrative example"))
        assumptions = None
        if mode != "Not costed":
            illustrative = mode == "Illustrative example"
            prefix = "office_example_" if illustrative else "office_entered_"
            assumptions = {"illustrative": illustrative}
            for name, label, default in [
                ("gross", "Annual gross benefit per controls-review room (£)", 1200.),
                ("running", "Annual controls support per reviewed room (£)", 150.),
                ("control_project", "One-off controls work per reviewed room (£)", 1800.),
                ("split_project", "One-off partition, fit-out and AV per split (£)", 12000.),
                ("extra_running", "Annual running cost per additional room (£)", 250.),
            ]:
                assumptions[name] = st.number_input(label, min_value=0., step=50.,
                    **u.field_state(prefix + name, default if illustrative else 0.))
            st.caption("Example amounts are invented for the webinar. Entered estimates are assumptions too. Benefit is a fixed amount per reviewed original room, not inferred from temperature, light or empty hours. New-room running costs are deducted; fit-out is shown separately.")
        st.caption("One programme budget replaces individual room cases here, avoiding duplicate projects and mixed currencies. No rent saving, avoided expansion or increased revenue is included.")
    return office_scenario(ctx, chosen, seats, assumptions)


def map_html(ctx, model):
    splits = {s["room"] for s in model["splits"]}
    controls = set(model["controls"])
    rooms = set(model["rooms"]["Room key"])
    if not office_map.applies(ctx):
        return ('<div class="office-no-map"><strong>One programme across the selected rooms</strong>'
                f'<b>{len(controls)}</b><span>rooms to review for operating changes</span>'
                '<small>The confirmed floorplan is available for London EC.</small></div>')
    marks, names, mapped = [], [], set()
    for spec in office_map.SPACES:
        room = "London EC / " + spec["sources"][0]
        if spec["kind"] != "room" or room not in rooms:
            continue
        mapped.add(room)
        kind = "split" if room in splits else "controls" if room in controls else "keep"
        marks.append(f'<span class="office-pin {kind}" style="left:{spec["x"]}%;top:{spec["y"]}%" title="{escape(spec["name"])}">{spec["id"]}</span>')
        names.append(f'<div><i class="{kind}">{spec["id"]}</i><span>{escape(spec["name"])}</span></div>')
    extra = len(rooms - mapped)
    return ('<div class="office-plan-layout"><div class="office-plan-image">'
            f'<img src="{office_map.picture()}" alt="London office with conceptual split candidates in purple and controls reviews in green"/>'
            + ''.join(marks) + '</div><div class="office-plan-key">' + ''.join(names)
            + f'<small>{extra} other room{ "s" if extra != 1 else ""} included in totals; not positioned.</small></div></div>')


def mix_html(model):
    scale = max([1, *model["before_mix"], *model["after_mix"]])
    rows = []
    for label, before, after in zip(["Focus · 1–2", "Small · 3–6", "Medium · 7–12", "Large · 13+"], model["before_mix"], model["after_mix"]):
        bars = ''.join(f'<div class="office-bar-line"><div class="office-bar-track"><i class="{kind}" style="width:{n/scale*100:.2f}%"></i></div><b>{n}</b></div>'
                       for kind, n in [("today", before), ("concept", after)])
        rows.append(f'<div class="office-mix-row"><span>{label}<small>seats</small></span><div>{bars}</div></div>')
    return ''.join(rows)


def calculation_panel(model):
    costs, assumptions = model["costs"], model["assumptions"]
    if not costs or not assumptions:
        st.html('<section class="connection-explainer"><h2>Benefit not costed</h2><p class="connection-intro">Open Presenter tools → Office programme costs to enter assumptions or choose the illustrative example.</p></section>')
        return
    controls, extra = len(model["controls"]), model["additional"]
    currency = lambda value: money(value, "GBP")
    basis = "Illustrative example" if costs["illustrative"] else "Entered estimates"
    lines = [
        ("Annual gross operating benefit", f'{controls} rooms × {currency(assumptions["gross"])}', controls * assumptions["gross"]),
        ("Annual controls support", f'{controls} rooms × {currency(assumptions["running"])}', -controls * assumptions["running"]),
        ("Annual running cost of extra rooms", f'{extra} rooms × {currency(assumptions["extra_running"])}', -extra * assumptions["extra_running"]),
    ]
    rows = ''.join(f'<div class="benefit-line"><span><b>{escape(label)}</b><small>{escape(detail)}</small></span><strong>{escape(currency(amount))}</strong></div>' for label, detail, amount in lines)
    st.html(f'<section class="connection-explainer benefit-explainer"><div class="connection-eyebrow">{escape(basis.upper())} · ANNUAL</div>'
        '<h2>Where the benefit comes from</h2><p class="connection-intro">A programme estimate based on the current room selection and assumptions.</p>'
        f'{rows}<div class="benefit-total"><span>Annual net benefit</span><strong>{escape(currency(costs["annual_net"]))}</strong></div>'
        f'<div class="benefit-investment"><b>One-off investment: {escape(currency(costs["project_cost"]))}</b><small>{controls} controls reviews × {escape(currency(assumptions["control_project"]))} + {extra} splits × {escape(currency(assumptions["split_project"]))}. Shown separately from annual net benefit.</small></div>'
        '<p class="connection-note"><b>Assumptions, not measured savings.</b> The gross benefit is an entered amount per room; temperature, light and empty hours do not calculate a cash saving. No rent saving or avoided expansion is included.</p></section>')


def render(ctx, case=None):
    model = scenario_inputs(ctx)
    costs, count = model["costs"], model["additional"]
    cost_basis = "Illustrative annual net benefit" if costs and costs["illustrative"] else "Estimated annual net benefit"
    net = money(costs["annual_net"], "GBP") if costs else "Not costed"
    cost_detail = f'{len(model["controls"])} controls-review rooms · after added running costs' if costs else "Set programme assumptions in Presenter tools"
    cards = [
        ("savings", cost_basis if costs else "Annual net operating benefit", net, cost_detail),
        ("capacity", "Concept additional rooms", f'+{count}', f'{model["before_count"]} today → {model["after_count"]} in concept · physical fit unverified'),
        ("fit", "Observed group fit", u.fmt(model["fit"], "%", 1), f'{len(model["ready"])} of {model["before_count"]} rooms qualify · occupied-time replay'),
    ]
    with st.container(key="office_opportunity"):
        for column, (kind, label, value, detail) in zip(st.columns(3, gap="small"), cards):
            with column, st.container(key="office_outcome_" + kind):
                st.html(f'<article class="office-outcome {kind}"><span>{escape(label)}</span><strong>{escape(value)}</strong><small>{escape(detail)}</small></article>')
                if kind == "savings":
                    with st.popover("View calculation", icon=":material/calculate:", width="stretch"):
                        calculation_panel(model)
        concepts = ''.join(f'<span><b>{escape(s["name"])}</b> {s["before"]} → {s["after"][0]} + {s["after"][1]} seats · {u.fmt(s["fit"], "%", 1)} fit</span>' for s in model["splits"])
        if not concepts:
            concepts = '<span>No room splits selected or supported for exploration in this scope.</span>'
        st.html('<div class="office-comparison"><section class="office-map-panel"><h2>Where to focus</h2>'
                + map_html(ctx, model)
                + '<div class="office-map-legend"><span><i class="split"></i>Explore a split</span><span><i class="controls"></i>Review controls</span><span><i class="keep"></i>Retain</span></div></section>'
                '<section class="office-mix-panel"><div class="office-mix-title"><h2>A different room mix</h2><div><i class="today"></i>Today <i class="concept"></i>Concept</div></div>'
                + mix_html(model) + f'<div class="office-split-summary">{concepts}</div>'
                '<p class="office-fit-note">Groups stay in their original room or its larger replacement. New bookings and simultaneous demand are not predicted.</p></section></div>')
        investment = f' · {money(costs["project_cost"], "GBP")} one-off investment' if costs else ''
        st.html(f'<section class="office-programme"><div><strong>One office programme · {len(model["controls"])} controls reviews + {count} concept split{"s" if count != 1 else ""}</strong>'
                f'<span>Workplace + Facilities + IT · Confirm dimensions, bookings and budget; then pilot and remeasure.</span></div>'
                f'<div><b>{"Illustrative costs" if costs and costs["illustrative"] else "Entered cost assumptions" if costs else "Costing required"}{escape(investment)}</b>'
                '<small>Potential avoided expansion is a separate benefit; no rent saving is claimed.</small></div></section>')
    with ctx["tools"].expander("Office evidence and validation"):
        st.write(f'{model["before_count"]} positive-capacity meeting rooms in the selected filters; {len(model["ready"])} pass the occupancy coverage checks. The selected room from Improve does not narrow these totals; the shared Rooms filter does.')
        st.write("The concept holds the total seat count constant while exploring two rooms in place of one. It does not establish that partitions, access, ventilation, fire routes or accessibility fit the building. A measured plan and professional design review are still required.")
        st.write(f'Fit weights valid occupied room-hours across qualifying rooms: {model["occupied"]:.1f} observed, {model["exceeds"]:.1f} exceed the largest proposed replacement. Missing observations remain unknown. High overall fit can hide individual peaks; review each changed room below.')
        st.write("No groups are moved between rooms, pooled across time or divided between the two replacements. Booking conflicts, rejected bookings, concurrent demand and room purpose must be checked before approval. Real employee and guest feedback should validate the pilot; synthetic feedback does not establish an improvement.")
        if model["splits"]:
            st.dataframe([{ "Room": s["room"], "Current seats": s["before"], "Concept seats": " + ".join(map(str, s["after"])),
                            "Observed fit %": s["fit"], "Hours exceeding": s["exceeds"], "Observed peak": s["peak"]} for s in model["splits"]], hide_index=True)
        st.write("Controls-review rooms: " + (", ".join(model["controls"]) or "None"))
        st.caption("Each controls-review room is counted once even if both warmth and light trigger a review. Neither condition proves energy use; validate controller state and meters before assigning a real saving. No changes are sent to the building.")
        if costs:
            st.write(f'Annual gross benefit {money(costs["annual_savings"], "GBP")} less added annual running costs {money(costs["annual_extra_cost"], "GBP")} = annual net benefit {money(costs["annual_net"], "GBP")}. One-off programme investment: {money(costs["project_cost"], "GBP")}.')
            st.caption("Operating benefit, extra meeting capacity and potential avoided expansion are distinct outcomes, not amounts to add together. All finances here are programme assumptions, not measured results.")
