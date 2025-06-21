import datetime as dt

import pytest
from django.core import mail as djmail
from django.test import override_settings
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretalx.common.models.log import ActivityLog
from pretalx.event.services import (
    periodic_event_services,
    task_periodic_event_services,
    task_periodic_schedule_export,
)


@pytest.mark.django_db
def test_task_periodic_event_created(event):
    djmail.outbox = []
    log = ActivityLog.objects.create(
        event=event, content_object=event, action_type="test"
    )
    assert str(event) in str(log)
    assert not event.settings.sent_mail_event_created
    task_periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert len(djmail.outbox) == 1
    assert event.settings.sent_mail_event_created
    task_periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert len(djmail.outbox) == 1


@pytest.mark.django_db
def test_task_periodic_event_created_long_ago(event):
    djmail.outbox = []
    with scopes_disabled():
        ActivityLog.objects.create(
            event=event, content_object=event, action_type="test"
        )
        ActivityLog.objects.filter(event=event).update(
            timestamp=now() - dt.timedelta(days=11)
        )
        event.cfp.deadline = now() - dt.timedelta(days=10)
        event.cfp.save()
    assert not event.settings.sent_mail_event_created
    task_periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert len(djmail.outbox) == 0, djmail.outbox[0].body
    assert not event.settings.sent_mail_event_created


@pytest.mark.django_db
def test_task_periodic_cfp_closed(event):
    djmail.outbox = []
    ActivityLog.objects.create(event=event, content_object=event, action_type="test")
    event.cfp.deadline = now() - dt.timedelta(hours=1)
    event.cfp.save()
    assert not event.settings.sent_mail_cfp_closed
    task_periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert len(djmail.outbox) == 2  # event created + deadline passed
    assert event.settings.sent_mail_cfp_closed
    task_periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert len(djmail.outbox) == 2


@pytest.mark.django_db
def test_task_periodic_event_over(event, slot):
    djmail.outbox = []
    ActivityLog.objects.create(event=event, content_object=event, action_type="test")
    event.date_to = now() - dt.timedelta(days=1)
    event.save()
    assert not event.settings.sent_mail_cfp_closed
    task_periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert len(djmail.outbox) == 2  # event created + event over
    assert event.settings.sent_mail_event_over
    task_periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert len(djmail.outbox) == 2


@pytest.mark.django_db
def test_task_periodic_event_over_no_talks(event):
    djmail.outbox = []
    ActivityLog.objects.create(event=event, content_object=event, action_type="test")
    event.date_to = now() - dt.timedelta(days=1)
    event.save()
    assert not event.settings.sent_mail_cfp_closed
    task_periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert len(djmail.outbox) == 1  # event created
    assert not event.settings.sent_mail_event_over
    task_periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert len(djmail.outbox) == 1


@pytest.mark.django_db
def test_periodic_event_services(event):
    djmail.outbox = []
    ActivityLog.objects.create(event=event, content_object=event, action_type="test")
    assert not event.settings.sent_mail_event_created
    periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert event.settings.sent_mail_event_created
    assert len(djmail.outbox) == 1


@pytest.mark.django_db
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "lalala",
        }
    }
)
@pytest.mark.parametrize("should_rebuild_schedule", (True, False))
def test_periodic_event_services_schedule_export(
    event, schedule, should_rebuild_schedule
):
    ActivityLog.objects.create(event=event, content_object=event, action_type="test")
    event.feature_flags["export_html_on_release"] = True
    event.save()
    event.cache.set("rebuild_schedule_export", should_rebuild_schedule)
    assert event.cache.get("rebuild_schedule_export") is should_rebuild_schedule
    periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert not event.cache.get("rebuild_schedule_export")


@pytest.mark.django_db
def test_periodic_event_fail():
    task_periodic_event_services("lololol")


@pytest.mark.django_db
def test_trigger_schedule_export_unnecessary(event):
    event.feature_flags["export_html_on_release"] = True
    event.save()
    timestamp = now() - dt.timedelta(minutes=10)
    event.cache.set("last_schedule_rebuild", timestamp)
    task_periodic_schedule_export(event.slug)


@pytest.mark.django_db
def test_trigger_schedule_export_regularly(event):
    event.feature_flags["export_html_on_release"] = True
    event.save()
    assert not event.cache.get("last_schedule_rebuild")
    task_periodic_schedule_export(event.slug)
