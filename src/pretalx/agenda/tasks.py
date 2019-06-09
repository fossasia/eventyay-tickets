import logging

from django_scopes import scope, scopes_disabled

from pretalx.celery_app import app
from pretalx.event.models import Event

LOGGER = logging.getLogger(__name__)


@app.task()
def export_schedule_html(*, event_id: int, make_zip=True):
    from django.core.management import call_command

    with scopes_disabled():
        event = Event.objects.prefetch_related('submissions').filter(pk=event_id).first()
    if not event:
        LOGGER.error(f'In export_schedule_html: Could not find Event ID {event_id}')
        return

    with scope(event=event):
        if not event.current_schedule:
            LOGGER.error(f'In export_schedule_html: Event {event.slug} has no schedule.')
            return

    cmd = ['export_schedule_html', event.slug]
    if make_zip:
        cmd.append('--zip')
    call_command(*cmd)
