"""Tests for the ticketing action button on the common event status page.

The status page must offer exactly one ticketing action: "Set up tickets" while
the event has no ticket type yet, and "Manage Tickets" once at least one exists.
"""

import pytest
from django.test import override_settings
from django.urls import reverse
from django_scopes import scopes_disabled


SET_UP_LABEL = 'Set up tickets'
MANAGE_LABEL = 'Manage Tickets'

TICKETING_MODES = ['public_sales', 'public_test', 'private_test', 'unpublished']


def apply_ticketing_mode(event, mode):
    """Put the event into one of the ticketing modes offered by the status page."""
    event.tickets_published = mode == 'public_sales'
    event.testmode = mode == 'public_test'
    event.private_testmode = mode == 'private_test'
    event.save()
    event.settings.set('private_testmode_tickets', mode == 'private_test')


@pytest.fixture
def live_url(event):
    return reverse(
        'eventyay_common:event.live',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )


@pytest.fixture
def setup_url(event):
    return reverse(
        'control:event.quick',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )


@pytest.fixture
def manage_url(event):
    return reverse(
        'control:event.products',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )


@pytest.fixture
def ticket_product(event):
    with scopes_disabled():
        return event.products.create(
            name='Early-bird ticket',
            default_price=23,
            admission=True,
        )


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_event_without_tickets_shows_only_setup_action(organizer_client, event, live_url, setup_url, manage_url):
    """An event with no ticket type offers "Set up tickets" and nothing else."""
    response = organizer_client.get(live_url)
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context['has_ticket_products'] is False
    assert SET_UP_LABEL in content
    assert MANAGE_LABEL not in content
    assert setup_url in content
    assert manage_url not in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_event_with_tickets_shows_only_manage_action(
    organizer_client, event, ticket_product, live_url, setup_url, manage_url
):
    """An event with a ticket type offers "Manage Tickets" and nothing else."""
    response = organizer_client.get(live_url)
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context['has_ticket_products'] is True
    assert MANAGE_LABEL in content
    assert SET_UP_LABEL not in content
    assert manage_url in content
    assert setup_url not in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_manage_action_shown_without_quota(organizer_client, event, ticket_product, live_url):
    """A ticket type alone flips the action, even though ticketing is not sellable yet."""
    response = organizer_client.get(live_url)
    content = response.content.decode()

    assert response.context['ticketing_ready'] is False
    assert MANAGE_LABEL in content
    assert SET_UP_LABEL not in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize('mode', TICKETING_MODES)
def test_setup_action_is_independent_of_ticketing_mode(organizer_client, event, live_url, mode):
    """Without a ticket type the setup action shows in every ticketing mode."""
    apply_ticketing_mode(event, mode)

    response = organizer_client.get(live_url)
    content = response.content.decode()

    assert SET_UP_LABEL in content
    assert MANAGE_LABEL not in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize('mode', TICKETING_MODES)
def test_manage_action_is_independent_of_ticketing_mode(organizer_client, event, ticket_product, live_url, mode):
    """With a ticket type the manage action shows in every ticketing mode."""
    apply_ticketing_mode(event, mode)

    response = organizer_client.get(live_url)
    content = response.content.decode()

    assert MANAGE_LABEL in content
    assert SET_UP_LABEL not in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize(
    ('mode', 'badge'),
    [
        ('public_sales', 'Public sales'),
        ('public_test', 'Public test mode'),
        ('private_test', 'Private test mode'),
        ('unpublished', 'Not published'),
    ],
)
def test_status_badge_stays_visible_next_to_either_action(
    organizer_client, event, ticket_product, live_url, mode, badge
):
    """The ticketing status badge is driven by the mode, not by the action button."""
    apply_ticketing_mode(event, mode)

    with_ticket = organizer_client.get(live_url).content.decode()
    assert badge in with_ticket
    assert MANAGE_LABEL in with_ticket

    with scopes_disabled():
        ticket_product.delete()

    without_ticket = organizer_client.get(live_url).content.decode()
    assert badge in without_ticket
    assert SET_UP_LABEL in without_ticket
