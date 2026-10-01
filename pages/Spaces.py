from workplace.views import spaces
from workplace.briefing import enabled, run

if enabled():
    run("Spaces")
else:
    spaces()
