from datetime import timedelta

from django.dispatch import receiver
from django.utils.timezone import now

from pretalx.celery_app import app
from pretalx.common.signals import periodic_task
from pretalx.event.models import Event


@app.task()
def task_periodic_event_services(event_slug):
    event = Event.objects.filter(slug=event_slug).prefetch_related('_settings_objects', 'submissions__slots').first()
    _now = now()
    if not event:
        return

    if not event.settings.sent_mail_event_created:
        if timedelta(0) <= (_now - event.log_entries.last().timestamp) <= timedelta(days=1):
            event.send_orga_mail(event.settings.mail_text_event_created)
            event.settings.sent_mail_event_created = True

    if not event.settings.sent_mail_cfp_closed and event.cfp.deadline:
        if timedelta(0) <= (_now - event.cfp.deadline) <= timedelta(days=1):
            event.send_orga_mail(event.settings.mail_text_cfp_closed)
            event.settings.sent_mail_cfp_closed = True

    if not event.settings.sent_mail_event_over:
        if (_now.date() + timedelta(days=3)) < (_now.date() + timedelta(days=1)) > event.date_to:
            if event.current_schedule and event.current_schedule.talks.filter(is_visible=True).count():
                event.send_orga_mail(event.settings.mail_text_event_over, stats=True)
                event.settings.sent_mail_event_over = True


@receiver(periodic_task)
def periodic_event_services(sender, **kwargs):
    for event in Event.objects.all().values_list('slug', flat=True):
        task_periodic_event_services.apply_async(args=(event, ))
