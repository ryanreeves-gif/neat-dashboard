"""Executive entry point: current state, room fit, experience and one next step."""

from workplace.views import overview
from workplace.briefing import enabled, run

if enabled():
    run("Overview")
else:
    overview()
