from datetime import timedelta

from django.dispatch import receiver
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from pretalx.agenda.management.commands.export_schedule_html import get_export_zip_path
from pretalx.agenda.tasks import export_schedule_html
from pretalx.celery_app import app
from pretalx.common.signals import periodic_task
from pretalx.event.models import Event


@app.task()
def task_periodic_event_services(event_slug):
    with scopes_disabled():
        event = (
            Event.objects.filter(slug=event_slug)
            .prefetch_related('_settings_objects', 'submissions__slots')
            .first()
        )
    if not event:
        return

    _now = now()
    with scope(event=event):
        event.build_initial_data()  # Make sure the required mail templates are there
        if not event.settings.sent_mail_event_created:
            if (
                timedelta(0)
                <= (_now - event.log_entries.last().timestamp)
                <= timedelta(days=1)
            ):
                event.send_orga_mail(event.settings.mail_text_event_created)
                event.settings.sent_mail_event_created = True

        if not event.settings.sent_mail_cfp_closed and event.cfp.deadline:
            if timedelta(0) <= (_now - event.cfp.deadline) <= timedelta(days=1):
                event.send_orga_mail(event.settings.mail_text_cfp_closed)
                event.settings.sent_mail_cfp_closed = True

        if not event.settings.sent_mail_event_over:
            if (
                (_now.date() - timedelta(days=3))
                <= event.date_to
                <= (_now.date() - timedelta(days=1))
            ):
                if (
                    event.current_schedule
                    and event.current_schedule.talks.filter(is_visible=True).count()
                ):
                    event.send_orga_mail(event.settings.mail_text_event_over, stats=True)
                    event.settings.sent_mail_event_over = True


@app.task()
def task_periodic_schedule_export(event_slug):
    with scopes_disabled():
        event = (
            Event.objects.filter(slug=event_slug)
            .prefetch_related('_settings_objects', 'submissions__slots')
            .first()
        )
    with scope(event=event):
        zip_path = get_export_zip_path(event)
        last_time = event.cache.get('last_schedule_rebuild')
        _now = now()
        should_rebuild_schedule = (
            event.cache.get('rebuild_schedule_export') or (
                event.settings.export_html_on_schedule_release and not zip_path.exists() and (
                    not last_time or now() - last_time > timedelta(days=1)
                )
            )
        )
        if should_rebuild_schedule:
            event.cache.delete('rebuild_schedule_export')
            event.cache.set('last_schedule_rebuild', _now, None)
            export_schedule_html.apply_async(kwargs={'event_id': event.id})


@receiver(periodic_task)
def periodic_event_services(sender, **kwargs):
    for event in Event.objects.all():
        with scope(event=event):
            task_periodic_event_services.apply_async(args=(event.slug,))
            if event.current_schedule:
                task_periodic_schedule_export.apply_async(args=(event.slug,))
            event.update_review_phase()
