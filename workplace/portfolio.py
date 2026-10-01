"""Room-level performance and improvement routes for the executive view.

Telemetry and synthetic feedback are joined for display, not causality. Neither
a low rating nor a vacancy condition authorises a control or construction change.
"""
from html import escape
from math import floor
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from workplace import conclusions as x

MIN_RESPONSES = 5
ROUTE_COLOURS = {"Controls + layout": "#5F259F", "Controls review": "#638C7D",
                 "Layout review": "#93ABB3", "Monitor": "#9F8884", "Evidence gap": "#C8D0D3"}


def room_portfolio(ctx, records):
    rooms = ctx["stats"].copy()
    scores = records.groupby("room_key").agg(Responses=("experience", "size"),
        Sentiment=("experience", "mean"), Equipment=("equipment", "mean"),
        Positive=("experience", lambda s: 100 * s.ge(4).mean()))
    rooms = rooms.merge(scores, left_on="Room key", right_index=True, how="left")
    rooms["Responses"] = rooms.Responses.fillna(0).astype(int)
    eligible = set(x.eligible_rooms(ctx)["Room key"])
    rooms["Usage eligible"] = rooms["Room key"].isin(eligible)
    rooms["Sentiment eligible"] = rooms.Responses.ge(MIN_RESPONSES)
    findings = x.improvement_summary(ctx)["issues"]
    for kind, name in [("fit", "Layout"), ("warm", "Warm"), ("light", "Light")]:
        selected = findings[findings.Kind.eq(kind)]
        rooms[name] = rooms["Room key"].isin(selected["Room key"])
        hours = selected.groupby("Room key")["Evidence hours"].max()
        rooms[name + " hours"] = rooms["Room key"].map(hours).fillna(0)
    rooms["Controls"] = rooms.Warm | rooms.Light
    rooms["Route"] = np.select([
        rooms["Coverage %"].fillna(0).lt(70), rooms.Controls & rooms.Layout, rooms.Controls, rooms.Layout,
    ], ["Evidence gap", "Controls + layout", "Controls review", "Layout review"], default="Monitor")
    return rooms


def room_leaders(portfolio, measure):
    if measure == "usage":
        eligible, score, decimals = "Usage eligible", "Utilisation %", 1
    elif measure == "sentiment":
        eligible, score, decimals = "Sentiment eligible", "Sentiment", 2
    else:
        raise ValueError("Choose usage or sentiment.")
    rows = portfolio[portfolio[eligible] & portfolio[score].notna()].copy()
    if rows.empty or (measure == "usage" and rows[score].max() <= 0):
        return rows.iloc[:0]
    shown = rows[score].round(decimals)
    return rows[shown.eq(shown.max())].sort_values("Room key")


def comparison_rows(portfolio):
    return portfolio[portfolio["Usage eligible"] & portfolio["Sentiment eligible"]].copy()


def room_label(name):
    # Short labels only; the full identity is retained in every hover and control.
    return str(name).split(" (")[0]


def performance_figure(portfolio, estate_utilisation, font):
    plotted = comparison_rows(portfolio)
    fig = go.Figure()
    y_floor = max(1, min(4, floor((float(plotted.Sentiment.min()) - .3) * 2) / 2)) if len(plotted) else 1
    split = float(estate_utilisation) if pd.notna(estate_utilisation) else 50
    # The reference lines organise the picture, they are not performance targets.
    fig.add_shape(type="rect", x0=0, x1=split, y0=4, y1=5.18, fillcolor="#F4F6F6", line_width=0, layer="below")
    fig.add_shape(type="rect", x0=split, x1=100, y0=4, y1=5.18, fillcolor="#EAF0ED", line_width=0, layer="below")
    fig.add_hline(y=4, line_dash="dot", line_color="#D5B68F", line_width=1)
    fig.add_vline(x=split, line_dash="dot", line_color="#93ABB3", line_width=1)
    for route, colour in ROUTE_COLOURS.items():
        group = plotted[plotted.Route.eq(route)].sort_values("Utilisation %")
        if group.empty:
            continue
        positions = ["top right" if value < 15 else "top left" if value > 80 else ("bottom center" if i % 2 else "top center")
                     for i, value in enumerate(group["Utilisation %"])]
        custom = [[escape(str(r["Room key"])), int(r.Responses), float(r["Coverage %"]), float(r.Capacity), escape(route)] for _, r in group.iterrows()]
        fig.add_trace(go.Scatter(x=group["Utilisation %"], y=group.Sentiment, name=route,
            mode="markers+text", text=[escape(room_label(n)) for n in group["Room Name"]], textposition=positions,
            textfont=dict(size=11, color="#33353C"), marker=dict(size=12 + 4 * np.sqrt(group.Capacity.clip(upper=36)),
            color=colour, opacity=.88, line=dict(color="white", width=2)), customdata=custom,
            hovertemplate="<b>%{customdata[0]}</b><br>Observed time in use: %{x:.1f}%<br>Sample space rating: %{y:.2f}/5<br>%{customdata[1]} invented responses<br>%{customdata[2]:.0f}% occupancy coverage · %{customdata[3]:g} seats<br>%{customdata[4]}<extra></extra>"))
    fig.update_layout(template="plotly_white", height=310, margin=dict(l=42, r=22, t=16, b=48),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="white", font=dict(family=font, size=11, color="#4C515C"),
        legend=dict(orientation="h", y=-.22, x=0, font_size=10, itemsizing="constant"), hoverlabel=dict(bgcolor="white"))
    fig.update_xaxes(range=[0, 100], title="Observed time in use (%)", dtick=20, ticksuffix="%", gridcolor="#ECEFF0", zeroline=False)
    fig.update_yaxes(range=[y_floor, 5.18], title="Sample space rating / 5", dtick=.5 if y_floor >= 3 else 1, gridcolor="#ECEFF0", zeroline=False)
    fig.update_layout(meta={"rooms": plotted["Room key"].tolist(), "rating_axis_floor": y_floor,
                            "use_reference": split, "sentiment_is_synthetic": True})
    return fig


def opportunity_rows(portfolio):
    rows = portfolio[portfolio.Controls | portfolio.Layout].copy()
    rows["Review routes"] = rows.Controls.astype(int) + rows.Layout.astype(int)
    return rows.sort_values(["Review routes", "Occupied hours", "Room key"], ascending=[False, False, True])


def opportunity_figure(portfolio, font):
    rows = opportunity_rows(portfolio)
    # Every row is a room, every coloured cell means a qualifying review signal.
    z = [[int(r.Controls), int(r.Layout)] for _, r in rows.iterrows()]
    custom = [[[escape(str(r["Room key"])), "Controls", bool(r.Controls), r["Coverage %"]],
               [escape(str(r["Room key"])), "Layout", bool(r.Layout), r["Coverage %"]]] for _, r in rows.iterrows()]
    fig = go.Figure(go.Heatmap(z=z, x=["Controls / BMS", "Room layout"],
        y=[escape(room_label(n)) for n in rows["Room Name"]], customdata=custom,
        text=[["Review" if cell else "—" for cell in row] for row in z], texttemplate="%{text}",
        textfont=dict(size=12), zmin=0, zmax=1, colorscale=[[0, "#F2F4F5"], [1, "#93ABB3"]],
        showscale=False, xgap=7, ygap=6,
        hovertemplate="%{customdata[0]}<br>%{customdata[1]} review signal: %{customdata[2]}<br>%{customdata[3]:.0f}% occupancy coverage<extra></extra>"))
    fig.update_layout(template="plotly_white", height=max(235, min(340, 75 + 29 * len(rows))),
        margin=dict(l=4, r=4, t=10, b=12), font=dict(family=font, size=11, color="#4C515C"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(side="top", showgrid=False)
    return fig
