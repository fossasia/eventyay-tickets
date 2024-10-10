import pytest
from pretix.base.models import Organizer, Event
from django.utils.timezone import now

@pytest.fixture
def event(db):
    organizer = Organizer.objects.create(name="Test Organizer", slug="test-organizer")
    event = Event.objects.create(
        organizer=organizer,
        name="Test Event",
        slug="test-event",
        live=True,
        date_from=now(),
    )
    return event
