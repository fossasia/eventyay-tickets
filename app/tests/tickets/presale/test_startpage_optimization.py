from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer
from eventyay.base.models.cfp import CfP
from eventyay.base.models.type import SubmissionType


@pytest.fixture
def startpage_events():
    with scopes_disabled():
        o = Organizer.objects.create(name='Test Organizer', slug='test-org')
        # Create featured event
        e_featured = Event.objects.create(
            organizer=o,
            name='Featured Event',
            slug='featured-1',
            date_from=now() + timedelta(days=5),
            live=True,
            is_public=True,
            startpage_visible=True,
            startpage_featured=True,
        )
        e_featured.settings.set('event_preview_image', 'http://example.com/hero.jpg')
        # Create upcoming event
        e_upcoming = Event.objects.create(
            organizer=o,
            name='Upcoming Event',
            slug='upcoming-1',
            date_from=now() + timedelta(days=10),
            live=True,
            is_public=True,
            startpage_visible=True,
            startpage_featured=False,
        )
        # Create past event
        e_past = Event.objects.create(
            organizer=o,
            name='Past Event',
            slug='past-1',
            date_from=now() - timedelta(days=10),
            date_to=now() - timedelta(days=9),
            live=True,
            is_public=True,
            startpage_visible=True,
            startpage_featured=False,
        )
        return o, e_featured, e_upcoming, e_past


@pytest.mark.django_db
def test_startpage_sections_rendering(startpage_events, client):
    response = client.get('/')
    assert response.status_code == 200
    content = response.content.decode('utf-8')
    assert 'Featured Event' in content
    assert 'Upcoming Event' in content
    assert 'Past Event' in content


@pytest.mark.django_db
def test_startpage_event_card_image_attributes(startpage_events, client):
    response = client.get('/')
    assert response.status_code == 200
    content = response.content.decode('utf-8')
    # Verify performance attributes on card elements
    assert 'decoding="async"' in content
    assert 'width="800"' in content
    assert 'height="450"' in content
    assert 'fetchpriority="high"' in content or 'loading="lazy"' in content


@pytest.mark.django_db
def test_startpage_bounded_query_scaling(startpage_events, client, django_assert_num_queries):
    o = startpage_events[0]
    # Create 30 additional past events in DB
    with scopes_disabled():
        for i in range(30):
            Event.objects.create(
                organizer=o,
                name=f'Bulk Past Event {i}',
                slug=f'bulk-past-{i}',
                date_from=now() - timedelta(days=20 + i),
                date_to=now() - timedelta(days=19 + i),
                live=True,
                is_public=True,
                startpage_visible=True,
            )

    response = client.get('/')
    assert response.status_code == 200
    ctx = response.context
    assert len(ctx['past_events']) <= 8
    assert len(ctx['upcoming_events']) <= 8
    assert len(ctx['featured_events']) <= 8


@pytest.mark.django_db
def test_startpage_keeps_featured_when_talks_testmode_false_and_other_true_setting(
    startpage_events, client
):
    """Regression: Django exclude(related__a, related__b) must not drop live events.

    Prod events often have talks_testmode=False stored plus unrelated True settings
    (plugins). The old exclude wrongly hid them from Featured/Upcoming.
    """
    _, e_featured, _, _ = startpage_events
    with scopes_disabled():
        e_featured.settings.set('talks_testmode', False)
        e_featured.settings.set('payment_stripe__enabled', True)

    response = client.get('/')
    assert response.status_code == 200
    names = [str(e.name) for e in response.context['featured_events']]
    assert 'Featured Event' in names

    upcoming = client.get('/upcoming/')
    assert upcoming.status_code == 200
    upcoming_names = [str(e.name) for e in upcoming.context['events']]
    assert 'Featured Event' in upcoming_names


@pytest.mark.django_db
def test_upcoming_cfp_open_filter_respects_session_type_deadlines(startpage_events, client):
    _, _, e_upcoming, _ = startpage_events
    with scopes_disabled():
        cfp = CfP.objects.filter(event=e_upcoming).first()
        cfp.deadline = now() - timedelta(days=1)
        cfp.save()
        for name in ('Lightning Talk', 'Workshop'):
            SubmissionType.objects.create(event=e_upcoming, name=name, deadline=now() + timedelta(days=7))
        assert CfP.objects.get(event=e_upcoming).is_open

    response = client.get('/upcoming/?cfp=open')
    assert response.status_code == 200
    names = [str(e.name) for e in response.context['events']]
    assert names.count('Upcoming Event') == 1


@pytest.mark.django_db
def test_startpage_hides_events_with_talks_testmode_true(startpage_events, client):
    _, e_featured, _, _ = startpage_events
    with scopes_disabled():
        e_featured.settings.set('talks_testmode', True)

    response = client.get('/')
    assert response.status_code == 200
    names = [str(e.name) for e in response.context['featured_events']]
    assert 'Featured Event' not in names
