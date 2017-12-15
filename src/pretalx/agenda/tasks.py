from pretalx.celery_app import app
from pretalx.event.models import Event


@app.task()
def export_schedule_html(*, event_id: int, make_zip=True):
    from django.core.management import call_command

    event = Event.objects.get(pk=event_id)

    cmd = [
        'export_schedule_html',
        event.slug,
    ]

    if make_zip:
        cmd.append('--zip')

    call_command(*cmd)
