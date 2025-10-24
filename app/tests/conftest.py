"""
Pytest fixtures for eventyay integration tests.
Provides test users, organizers, events, and authenticated clients.
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a regular test user."""
    return User.objects.create_user(
        email='testuser@example.com',
        password='testpass123',
        fullname='Test User',
        locale='en',
    )


@pytest.fixture
def staff_user(db):
    """Create a staff user with elevated permissions."""
    return User.objects.create_user(
        email='staff@example.com',
        password='staffpass123',
        fullname='Staff User',
        locale='en',
        is_staff=True,
    )


@pytest.fixture
def organizer(db):
    """Create a test organizer."""
    from eventyay.base.models import Organizer
    return Organizer.objects.create(
        name='Test Organizer',
        slug='testorg',
    )


@pytest.fixture
def event(db, organizer):
    """Create a test event with basic configuration."""
    from eventyay.base.models import Event
    now = timezone.now()
    return Event.objects.create(
        organizer=organizer,
        name='Test Event',
        slug='testevent',
        date_from=now + timedelta(days=30),
        date_to=now + timedelta(days=32),
        currency='USD',
        locale='en',
        is_public=True,
        live=True,
    )


@pytest.fixture
def team(db, organizer, user):
    """Create a team and add user as member."""
    from eventyay.base.models import Team
    team = Team.objects.create(
        organizer=organizer,
        name='Test Team',
        all_events=True,
        can_create_events=True,
        can_change_teams=True,
        can_manage_gift_cards=True,
        can_change_organizer_settings=True,
        can_change_event_settings=True,
        can_change_items=True,
        can_view_orders=True,
        can_change_orders=True,
        can_view_vouchers=True,
        can_change_vouchers=True,
    )
    team.members.add(user)
    return team


@pytest.fixture
def client():
    """Return a Django test client."""
    return Client()


@pytest.fixture
def authenticated_client(client, user):
    """Return a client authenticated as regular user."""
    client.force_login(user)
    return client


@pytest.fixture
def staff_client(client, staff_user):
    """Return a client authenticated as staff user."""
    client.force_login(staff_user)
    return client


@pytest.fixture
def organizer_client(client, user, team):
    """Return a client authenticated as organizer team member."""
    client.force_login(user)
    return client
