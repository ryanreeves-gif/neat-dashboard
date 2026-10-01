from workplace.views import environment
from workplace.briefing import enabled, run

if enabled():
    run("Environment")
else:
    environment()
