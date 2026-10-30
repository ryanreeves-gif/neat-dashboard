"""Executive entry point: technology, environment, experience and practical next steps."""

from workplace.views import overview
from workplace.briefing import enabled, run

if enabled():
    run("Technology")
else:
    overview()
