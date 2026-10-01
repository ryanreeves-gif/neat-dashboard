from workplace.views import overview
from workplace.briefing import enabled, run

if enabled():
    run("Overview")
else:
    overview()
