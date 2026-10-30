"""Webinar journey: current state, room fit, experience, improve and office opportunity."""

from workplace.views import overview
from workplace.briefing import enabled, run

if enabled():
    run("Overview")
else:
    overview()
