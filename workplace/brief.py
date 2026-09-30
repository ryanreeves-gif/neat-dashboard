"""A single-page, filter-aware PDF brief. No financial outcomes are invented."""
from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path

import pandas as pd
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph

from workplace.executive import decision_actions, evidence_summary

FONT_DIR = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("BriefSans", str(FONT_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("BriefSansBold", str(FONT_DIR / "VeraBd.ttf")))


def _text(value):
    return str(value).replace("–", "-").replace("—", "-").replace("≤", "<=").replace("\u2011", "-")


def _short(value, maximum=100):
    value = _text(value)
    return value if len(value) <= maximum else value[:maximum-3] + "..."


def _number(value, suffix="", digits=0):
    return "Unknown" if pd.isna(value) else f"{value:,.{digits}f}{suffix}"


def pdf_brief(ctx):
    stream = BytesIO()
    width, height = A4
    pdf = Canvas(stream, pagesize=A4, pageCompression=1)
    pdf.setTitle("Neat | Workplace decision brief")
    pdf.setAuthor("Neat Workplace dashboard")
    ink, muted, blue = "#333333", "#4C515C", "#5274B8"
    margin, inner = 34, width-68
    q, s = evidence_summary(ctx), ctx["summary"]

    def box(x, top, w, h, fill):
        pdf.setFillColor(colors.HexColor(fill))
        pdf.roundRect(x, top-h, w, h, 9, stroke=0, fill=1)

    def paragraph(text, x, top, w, size=9, bold=False, colour=ink, max_height=None):
        text = escape(_text(text))
        while True:
            style = ParagraphStyle("brief", fontName="BriefSansBold" if bold else "BriefSans",
                                   fontSize=size, leading=size*1.23, textColor=colors.HexColor(colour))
            item = Paragraph(text, style)
            _, h = item.wrap(w, 1000)
            if max_height is None or h <= max_height:
                break
            size -= .2
            if size < 7.7:
                raise ValueError("Brief content exceeded its one-page layout")
        item.drawOn(pdf, x, top-h)
        return top-h

    paragraph("neat.", margin, height-30, 100, 27)
    paragraph("WORKPLACE / DECISION BRIEF", width-254, height-38, 220, 8, True, muted)
    paragraph("Your workplace. Next steps.", margin, 773, inner, 23, True)
    locations = ", ".join(sorted(ctx["inventory"].Location.unique()))
    hours = "Mon-Fri 08:00-19:00" if ctx["office"] else "All hours"
    scope = (f"{_short(locations, 75)} | {s['rooms']} monitored rooms | {hours}\n"
             f"{ctx['start']:%d %b %Y %H:%M} - {ctx['end']:%d %b %Y %H:%M} | Recorded source time")
    paragraph(scope.replace("\n", " · "), margin, 741, inner, 9, max_height=30)

    box(margin, 706, inner, 78, "#FFF1DD" if q["tone"] == "limited" else "#EBF0F7")
    paragraph(q["label"], margin+12, 695, inner-24, 10.5, True)
    paragraph(f"Occupancy coverage: {_number(q['coverage'], '%')} | {s['valid_hours']:,.1f} of "
              f"{s['expected_hours']:,.1f} scheduled room-hours | {q['rooms_ready']}/{q['rooms_total']} rooms at 70%+",
              margin+12, 677, inner-24, 8.8, max_height=22)
    latest = "Unknown" if pd.isna(q["latest"]) else f"{q['latest']:%d %b %Y %H:%M}"
    paragraph(f"Latest source reading for selected rooms: {latest} (recorded source time).",
              margin+12, 654, inner-24, 8.3)
    note = "Generated sample data; not customer evidence." if ctx.get("demo") else "Coverage measures completeness, not accuracy. Missing data is not empty-room time."
    paragraph(note, margin+12, 640, inner-24, 8, colour=muted)

    metric_width = (inner-16)/3
    metrics = [("ROOMS MONITORED", str(s["rooms"]), "Selected rooms only"),
               ("TIME IN USE", _number(s["utilisation"], "%"), "Share of valid observed time"),
               ("TYPICAL ATTENDANCE", _number(s["attendance"], digits=1), "People, when occupied")]
    for i, (label, value, detail) in enumerate(metrics):
        x = margin + i*(metric_width+8)
        box(x, 615, metric_width, 62, "#F4F5F6")
        paragraph(label, x+10, 606, metric_width-20, 7.5, True, muted)
        paragraph(value, x+10, 592, metric_width-20, 21, True, blue)
        paragraph(detail, x+10, 566, metric_width-20, 7.6, colour=muted)

    paragraph("Decisions to explore", margin, 539, inner, 15, True)
    paragraph("Data readiness first; room candidates ordered by evidence hours, not financial return.",
              margin, 519, inner, 8, colour=muted)
    top = 501
    for i, action in enumerate(decision_actions(ctx)):
        box(margin, top, inner, 108, "#F4F5F6")
        paragraph(f"{i+1:02d}  {action['title']}", margin+12, top-10, inner-24, 11, True)
        left_width = 302
        left_top = paragraph(_short(action["scope"], 85), margin+12, top-28, left_width, 8, True, blue, 20)
        left_top = paragraph("Evidence: " + action["evidence"], margin+12, left_top-4, left_width, 8.5, max_height=24)
        paragraph("Next: " + action["action"], margin+12, left_top-4, left_width, 8.5, max_height=34)
        rx, rw = margin+left_width+26, inner-left_width-38
        paragraph("Potential benefit: " + action["benefit"], rx, top-29, rw, 8.5, max_height=43)
        paragraph("Owner: " + action["owner"], rx, top-77, rw, 8)
        paragraph("Cost: " + action["cost"], rx, top-91, rw, 8, True)
        top -= 116

    # Fixed footer region keeps short and full briefs equally easy to compare.
    paragraph("Before approving an investment", margin, 143, inner, 11, True)
    method = ("Validate peak demand, room purpose and accessibility. Bookings, employee feedback, building controls "
              "and energy meters are not connected. Costs and savings have not been assessed. Agree a baseline, "
              "owner, budget and employee outcome, then review a small pilot before expanding it.")
    paragraph(method, margin, 126, inner, 8.5, max_height=42)
    assumptions = ("Time in use = occupied / valid observed hours. Typical attendance excludes observed empty periods. "
                   "Hourly capacity used on Spaces includes them. Source timezones are not mapped per office.")
    if q["status_unreported"]:
        assumptions += " Device status is unreported for some records."
    paragraph(assumptions, margin, 78, inner, 7.9, colour=muted, max_height=31)
    pdf.setStrokeColor(colors.HexColor("#DCE2E8"))
    pdf.line(margin, 39, width-margin, 39)
    paragraph("Neat Workplace | Investigation brief | Full evidence and thresholds are in the dashboard", margin, 31, inner-30, 7.4, colour=muted)
    paragraph("1 / 1", width-margin-28, 31, 28, 7.4, colour=muted)
    pdf.showPage()
    pdf.save()
    return stream.getvalue()
