import pytest
from django.conf import settings
from django.utils.timezone import now

from pretix.base.models import Event, Organizer


@pytest.fixture
def event():
    o = Organizer.objects.create(name='MRMCD', slug='mrmcd')
    event = Event.objects.create(
        organizer=o,
        name='MRMCD2015',
        slug='2015',
        date_from=now(),
    )
    settings.SITE_URL = 'http://example.com'
    return event
