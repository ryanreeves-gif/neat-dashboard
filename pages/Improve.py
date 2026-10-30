"""The recommended actions and illustrative control response."""
from workplace.views import environment
from workplace.briefing import enabled, run

if enabled():
    run("Improve")
else:
    environment()
