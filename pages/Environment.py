"""Room evidence and interactive, local-only building-control scenarios."""

from workplace.views import environment
from workplace.briefing import enabled, run

if enabled():
    run("Environment")
else:
    environment()
