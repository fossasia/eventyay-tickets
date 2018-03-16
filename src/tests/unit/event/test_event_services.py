from datetime import timedelta

import pytest
from django.core import mail as djmail
from django.utils.timezone import now

from pretalx.common.models.log import ActivityLog
from pretalx.event.services import (
    periodic_event_services, task_periodic_event_services,
)


@pytest.mark.django_db
def test_task_periodic_event_created(event):
    djmail.outbox = []
    ActivityLog.objects.create(event=event, content_object=event, action_type='test')
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
    ActivityLog.objects.create(event=event, content_object=event, action_type='test')
    ActivityLog.objects.filter(event=event).update(timestamp=now() - timedelta(days=11))
    event.cfp.deadline = now() - timedelta(days=10)
    event.cfp.save()
    assert not event.settings.sent_mail_event_created
    task_periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert len(djmail.outbox) == 0, djmail.outbox[0].body
    assert not event.settings.sent_mail_event_created


@pytest.mark.django_db
def test_task_periodic_cfp_closed(event):
    djmail.outbox = []
    ActivityLog.objects.create(event=event, content_object=event, action_type='test')
    event.cfp.deadline = now() - timedelta(hours=1)
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
    ActivityLog.objects.create(event=event, content_object=event, action_type='test')
    event.date_to = now() - timedelta(days=1)
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
    ActivityLog.objects.create(event=event, content_object=event, action_type='test')
    event.date_to = now() - timedelta(days=1)
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
    ActivityLog.objects.create(event=event, content_object=event, action_type='test')
    assert not event.settings.sent_mail_event_created
    periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert event.settings.sent_mail_event_created
    assert len(djmail.outbox) == 1


@pytest.mark.django_db
def test_periodic_event_fail():
    task_periodic_event_services('lololol')
