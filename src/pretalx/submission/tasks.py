import logging

from django_scopes import scope, scopes_disabled

from pretalx.celery_app import app
from pretalx.event.models import Event

LOGGER = logging.getLogger(__name__)


@app.task()
def recalculate_all_review_scores(*, event_id: int):
    with scopes_disabled():
        event = (
            Event.objects.prefetch_related("submissions").filter(pk=event_id).first()
        )
    if not event:
        LOGGER.error(f"Could not find Event ID {event_id} for export.")
        return

    with scope(event=event):
        for submission in event.submissions.all():
            submission.update_review_scores()
