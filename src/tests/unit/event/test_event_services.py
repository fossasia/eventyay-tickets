import pytest

from pretalx.common.models.log import ActivityLog
from pretalx.event.services import (
    periodic_event_services, task_periodic_event_services,
)


@pytest.mark.django_db
def test_task_periodic_event(event):
    ActivityLog.objects.create(event=event, content_object=event, action_type='test')
    assert not event.settings.sent_mail_event_created
    task_periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert event.settings.sent_mail_event_created


@pytest.mark.django_db
def test_periodic_event_services(event):
    ActivityLog.objects.create(event=event, content_object=event, action_type='test')
    assert not event.settings.sent_mail_event_created
    periodic_event_services(event.slug)
    event = event.__class__.objects.get(slug=event.slug)
    assert event.settings.sent_mail_event_created
