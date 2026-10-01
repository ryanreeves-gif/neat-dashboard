"""Experience results with an immediately available companion survey."""

from workplace.feedback_view import feedback_page
from workplace.briefing import enabled, run

if enabled():
    run("Feedback")
else:
    feedback_page()
