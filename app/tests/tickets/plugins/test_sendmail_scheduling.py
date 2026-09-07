import datetime
from unittest.mock import patch

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Order, OrderPosition, Product, Team, User
from eventyay.plugins.sendmail.models import EmailQueue


@pytest.fixture
def organizer(db):
    return Organizer.objects.create(name='Sendmail Test Org', slug='sm-test-org')


@pytest.fixture
def event(organizer):
    return Event.objects.create(
        organizer=organizer,
        name='Sendmail Test Event',
        slug='sm-test-event',
        date_from=now() + datetime.timedelta(days=7),
        locale='en',
    )


@pytest.fixture
def product(event):
    return Product.objects.create(
        name='Standard Ticket',
        event=event,
        default_price=10,
    )


@pytest.fixture
def pending_order(product):
    order = Order.objects.create(
        event=product.event,
        status=Order.STATUS_PENDING,
        expires=now() + datetime.timedelta(days=1),
        total=10,
        code='SMTEST',
        email='attendee@example.com',
        datetime=now(),
        locale='en',
        require_approval=False,
    )
    OrderPosition.objects.create(order=order, product=product, price=10)
    return order


@pytest.fixture
def staff_user(event):
    user = User.objects.create_user('sm_staff@example.com', 'password123')
    team = Team.objects.create(
        organizer=event.organizer,
        name='Sendmail team',
        can_change_event_settings=True,
        all_events=True,
    )
    team.members.add(user)
    return user


@pytest.fixture
def logged_client(client, staff_user):
    client.force_login(staff_user)
    return client


@pytest.fixture
def sendmail_url(event):
    return f'/control/event/{event.organizer.slug}/{event.slug}/sendmail/'


def _future_dt():
    return now() + datetime.timedelta(days=1)


def _base_post_data(product):
    """Minimal valid POST body for SenderView (no scheduled_at)."""
    return {
        'recipients': 'orders',
        'order_status': ['na'],
        'subject_0': 'Test subject',
        'text_0': 'Hello attendee.',
        'products': [str(product.pk)],
        'browser_timezone': 'UTC',
    }


@pytest.mark.django_db
def test_scheduled_email_not_sent_immediately(
    logged_client, sendmail_url, product, pending_order
):
    """
    POSTing with a future scheduled_at must create an EmailQueue row whose
    sent_at is NULL – the email is queued, not delivered immediately.
    """
    future = _future_dt()
    data = _base_post_data(product)
    data['scheduled_at_0'] = future.strftime('%Y-%m-%d')
    data['scheduled_at_1'] = future.strftime('%H:%M:%S')

    initial_scheduled_count = EmailQueue.objects.filter(scheduled_at__isnull=False).count()

    with patch('eventyay.plugins.sendmail.views.send_queued_mail') as mock_task:
        mock_task.apply_async = lambda *a, **kw: None
        with scopes_disabled():
            response = logged_client.post(sendmail_url, data, follow=True)

    assert response.status_code == 200, response.content[:500]

    with scopes_disabled():
        new_scheduled_count = EmailQueue.objects.filter(scheduled_at__isnull=False).count()
        assert new_scheduled_count > initial_scheduled_count, "Expected a new scheduled EmailQueue row"

        qm = EmailQueue.objects.order_by('-created_at').first()
        assert qm.sent_at is None, "Scheduled email must not be sent immediately (sent_at should be NULL)"
        assert qm.scheduled_at is not None


@pytest.mark.django_db
def test_scheduling_dispatches_celery_task_with_eta(
    logged_client, sendmail_url, product, pending_order
):
    """
    When a future scheduled_at is submitted, send_queued_mail.apply_async
    must be called with eta=scheduled_at so delivery happens at the right time.
    """
    future = _future_dt()
    data = _base_post_data(product)
    data['scheduled_at_0'] = future.strftime('%Y-%m-%d')
    data['scheduled_at_1'] = future.strftime('%H:%M:%S')

    captured_kwargs = {}

    def _capture(*args, **kwargs):
        captured_kwargs.update(kwargs)

    with patch(
        'eventyay.plugins.sendmail.views.send_queued_mail.apply_async',
        side_effect=_capture,
    ):
        with scopes_disabled():
            response = logged_client.post(sendmail_url, data, follow=True)

    assert response.status_code == 200

    assert 'eta' in captured_kwargs, "apply_async must be called with 'eta'"
    dispatched_eta = captured_kwargs['eta']
    delta = abs((dispatched_eta - future).total_seconds())
    assert delta < 120, f"ETA {dispatched_eta!r} deviates too far from requested {future!r}"


@pytest.mark.django_db
def test_past_scheduled_at_rejected_by_form(
    logged_client, sendmail_url, product
):
    """
    Submitting a scheduled_at in the past must fail form validation and
    return a page with an error (no EmailQueue row created).
    """
    past = now() - datetime.timedelta(hours=2)
    data = _base_post_data(product)
    data['scheduled_at_0'] = past.strftime('%Y-%m-%d')
    data['scheduled_at_1'] = past.strftime('%H:%M:%S')

    before = EmailQueue.objects.count()

    with scopes_disabled():
        response = logged_client.post(sendmail_url, data)

    assert response.status_code in (200, 302)

    with scopes_disabled():
        after = EmailQueue.objects.count()

    assert after == before, "No EmailQueue row should be created for a past scheduled_at"
