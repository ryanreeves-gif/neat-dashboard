"""Supporting room-performance overview retained outside the short demo route."""
from workplace.views import overview
from workplace.briefing import enabled, run

if enabled():
    run("Overview")
else:
    overview()
