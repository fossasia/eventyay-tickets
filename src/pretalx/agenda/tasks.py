import logging

from pretalx.celery_app import app
from pretalx.event.models import Event

logger = logging.getLogger(__name__)


@app.task()
def export_schedule_html(*, event_id: int, make_zip=True):
    from django.core.management import call_command

    event = Event.objects.filter(pk=event_id).first()
    if not event:
        logger.error(f'In export_schedule_html: Could not find Event ID {event_id}')
        return

    cmd = [
        'export_schedule_html',
        event.slug,
    ]

    if make_zip:
        cmd.append('--zip')

    call_command(*cmd)
