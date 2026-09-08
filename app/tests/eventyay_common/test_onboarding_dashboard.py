"""Tests for the new-user onboarding dashboard."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from eventyay.base.models import Event, Organizer, Team
from eventyay.base.meetup import EVENT_TYPE_SETTING, MEETUP_EVENT_TYPE
from eventyay.eventyay_common.onboarding import (
    _event_kind,
    format_profile_incomplete_message,
    get_missing_profile_fields,
    is_profile_incomplete,
    user_needs_onboarding,
)

User = get_user_model()


@pytest.fixture
def new_user(db):
    return User.objects.create_user(
        email='newuser@example.com',
        password='testpass123',
        locale='en',
    )


@pytest.fixture
def new_user_client(client, new_user):
    client.force_login(new_user)
    return client


@pytest.fixture
def public_upcoming_event(db):
    organizer = Organizer.objects.create(name='Public Org', slug='public-org')
    now = timezone.now()
    return Event.objects.create(
        organizer=organizer,
        name='Public Summit',
        slug='public-summit',
        date_from=now + timedelta(days=40),
        date_to=now + timedelta(days=42),
        currency='EUR',
        locale='en',
        is_public=True,
        live=True,
        startpage_visible=True,
        testmode=False,
        email='org@example.com',
    )


@pytest.mark.django_db
def test_new_user_needs_onboarding(new_user):
    assert user_needs_onboarding(new_user, request=None) is True
    assert is_profile_incomplete(new_user) is True
    assert get_missing_profile_fields(new_user) == ['full name', 'profile picture']
    assert 'full name' in format_profile_incomplete_message(get_missing_profile_fields(new_user))
    assert 'profile picture' in format_profile_incomplete_message(get_missing_profile_fields(new_user))


@pytest.mark.django_db
def test_profile_prompt_lists_only_missing_fields(new_user):
    new_user.fullname = 'Ada Lovelace'
    new_user.save(update_fields=['fullname'])
    missing = get_missing_profile_fields(new_user)
    assert missing == ['profile picture']
    assert format_profile_incomplete_message(missing) == (
        'Add your profile picture to finish your profile.'
    )


@pytest.mark.django_db
def test_user_with_organised_event_skips_onboarding(user, team, event):
    assert user_needs_onboarding(user, request=None) is False


@pytest.mark.django_db
def test_onboarding_dashboard_renders_for_new_user(new_user_client, public_upcoming_event):
    url = reverse('eventyay_common:dashboard')
    response = new_user_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'common-dashboard' in content
    assert 'Welcome to Eventyay!' in content
    assert 'Find events' in content
    assert 'Get started' in content
    assert 'Recommended events' in content
    assert 'Public Summit' in content
    assert 'Your upcoming events' not in content
    assert 'Complete your profile' in content
    assert 'Add your full name and profile picture to finish your profile.' in content


@pytest.mark.django_db
def test_onboarding_hides_organise_card_without_create_permission(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    assert 'Organise an event' not in content
    assert 'Attend an event' in content
    assert 'Submit a talk' in content


@pytest.mark.django_db
def test_onboarding_shows_organise_card_with_create_permission(new_user, new_user_client):
    organizer = Organizer.objects.create(name='Create Org', slug='create-org')
    team = Team.objects.create(
        organizer=organizer,
        name='Creators',
        can_create_events=True,
        all_events=False,
    )
    team.members.add(new_user)

    response = new_user_client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    assert 'Organise an event' in content
    assert reverse('eventyay_common:events.add') in content


@pytest.mark.django_db
def test_organiser_dashboard_still_shown_for_event_managers(organizer_client, event):
    response = organizer_client.get(reverse('eventyay_common:dashboard'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Welcome to Eventyay!' not in content
    assert 'Your upcoming events' in content
    assert 'common-dashboard' in content
    assert 'cd-event-card' in content
    assert 'Quick actions' in content


@pytest.mark.django_db
def test_orders_empty_state(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:orders'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No tickets yet' in content
    assert 'Browse events' in content
    assert 'No tickets match your filters.' not in content


@pytest.mark.django_db
def test_orders_empty_state_ignores_pagination_query(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:orders'), {'page': '1'})
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No tickets yet' in content
    assert 'No tickets match your filters.' not in content


@pytest.mark.django_db
def test_orders_empty_state_ignores_blank_filter_values(new_user_client):
    response = new_user_client.get(
        reverse('eventyay_common:orders'),
        {'code': '', 'status': '', 'date_from': '', 'date_to': ''},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No tickets yet' in content
    assert 'No tickets match your filters.' not in content


@pytest.mark.django_db
def test_orders_no_match_message_when_filter_active(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:orders'), {'code': 'NOMATCH'})
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No tickets match your filters.' in content
    assert 'No tickets yet' not in content


@pytest.mark.django_db
def test_sessions_empty_state(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:sessions'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No sessions yet' in content
    assert 'Find open calls' in content
    assert 'No sessions match your filters.' not in content


@pytest.mark.django_db
def test_sessions_empty_state_ignores_pagination_and_blank_search(new_user_client):
    response = new_user_client.get(
        reverse('eventyay_common:sessions'),
        {'page': '1', 'search': ''},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No sessions yet' in content
    assert 'No sessions match your filters.' not in content


@pytest.mark.django_db
def test_sessions_no_match_message_when_filter_active(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:sessions'), {'search': 'nomatch'})
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No sessions match your filters.' in content
    assert 'No sessions yet' not in content


@pytest.mark.django_db
def test_private_events_are_not_recommended(new_user_client, db):
    organizer = Organizer.objects.create(name='Private Org', slug='private-org')
    now = timezone.now()
    Event.objects.create(
        organizer=organizer,
        name='Secret Meetup',
        slug='secret-meetup',
        date_from=now + timedelta(days=20),
        date_to=now + timedelta(days=21),
        currency='EUR',
        locale='en',
        is_public=False,
        live=True,
        startpage_visible=True,
        testmode=False,
        email='private@example.com',
    )
    response = new_user_client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    assert 'Secret Meetup' not in content


@pytest.mark.django_db
def test_global_navigation_labels(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    assert 'Browse events' in content
    assert 'My Tickets' in content
    assert 'Dashboard' in content


@pytest.mark.django_db
def test_event_kind_labels_event_series_and_meetup(event):
    assert _event_kind(event)['kind'] == 'event'
    assert _event_kind(event)['label'] == 'Event'

    event.has_subevents = True
    assert _event_kind(event)['kind'] == 'series'
    assert _event_kind(event)['label'] == 'Series'

    event.has_subevents = False
    event.settings.set(EVENT_TYPE_SETTING, MEETUP_EVENT_TYPE)
    assert _event_kind(event)['kind'] == 'meetup'
    assert _event_kind(event)['label'] == 'Meetup'
