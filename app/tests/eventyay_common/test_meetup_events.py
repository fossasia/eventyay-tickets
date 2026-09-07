from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import stripe
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils import timezone
from django.utils.crypto import get_random_string
from django_scopes import scopes_disabled

from eventyay.base.meetup import (
    get_rsvp_product_and_quota,
    provision_meetup_event,
)
from eventyay.base.models import Event, Order, OrderPayment, OrderPosition, Team, User
from eventyay.base.payment import StripePaymentProvider
from eventyay.eventyay_common.forms.event import EventCommonSettingsForm, EventUpdateForm
from eventyay.presale.views.event import EventIndex, JoinOnlineVideoView
from eventyay.presale.views.meetup import (
    MEETUP_RSVP_SESSION_KEY,
    MeetupRsvpView,
)


@pytest.fixture
def meetup_event(db, organizer):
    now = timezone.now()
    event = Event.objects.create(
        organizer=organizer,
        name='Meetup Event Test',
        slug='meetup-event-test',
        date_from=now + timedelta(days=10),
        date_to=now + timedelta(days=10, hours=2),
        currency='USD',
        locale='en',
        is_public=True,
        live=True,
        email='organizer@example.com',
    )
    with scopes_disabled():
        provision_meetup_event(event)
    return event


def create_paid_order(event, product, email, name='Test Attendee', code=None):
    order_code = code or get_random_string(5).upper()
    with scopes_disabled():
        order = Order.objects.create(
            event=event,
            email=email,
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            expires=timezone.now(),
            total=Decimal('0.00'),
            sales_channel='web',
            locale='en',
            code=order_code,
        )
        pos = OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('0.00'),
            positionid=1,
            attendee_email=email,
            attendee_name_parts={'_legacy': name},
        )
        pos.save()
        return order


@pytest.mark.django_db
@scopes_disabled()
def test_settings_form_initial_and_save_updates_quota_size(meetup_event):
    """Settings form loads initial from RSVP quota and updates quota size on save."""
    product, quota = get_rsvp_product_and_quota(meetup_event)
    assert quota is not None
    quota.size = 25
    quota.save(update_fields=['size'])

    form = EventCommonSettingsForm(obj=meetup_event)
    assert form.initial['registration_limit'] == 25

    data = form.initial.copy()
    data['registration_limit'] = 50
    data.setdefault('timezone', 'UTC')
    data.setdefault('locale', 'en')
    data.setdefault('locales', ['en'])
    bound_form = EventCommonSettingsForm(data=data, obj=meetup_event)
    assert bound_form.is_valid(), bound_form.errors
    bound_form.save()

    product, quota = get_rsvp_product_and_quota(meetup_event)
    assert quota.size == 50


@pytest.mark.django_db
@scopes_disabled()
def test_settings_form_updates_meetup_visibility(organizer):
    now = timezone.now()
    event = Event.objects.create(
        organizer=organizer,
        name='Toggle Privacy Meetup',
        slug='toggle-privacy-meetup',
        date_from=now + timedelta(days=10),
        date_to=now + timedelta(days=10, hours=2),
        currency='USD',
        locale='en',
    )
    provision_meetup_event(event, is_private=True)
    assert event.live is True
    assert event.tickets_published is True
    assert event.is_public is False
    assert event.settings.get('meta_noindex', as_type=bool) is True

    form = EventCommonSettingsForm(obj=event)
    assert form.initial['privacy_type'] == 'private'

    data = form.initial.copy()
    data['privacy_type'] = 'public'
    data.setdefault('timezone', 'UTC')
    data.setdefault('locale', 'en')
    data.setdefault('locales', ['en'])
    bound_form = EventCommonSettingsForm(data=data, obj=event)
    assert bound_form.is_valid(), bound_form.errors
    bound_form.save()

    event.refresh_from_db()
    assert event.live is True
    assert event.tickets_published is True
    assert event.is_public is True
    assert event.settings.get('meta_noindex', as_type=bool) is False

    form2 = EventCommonSettingsForm(obj=event)
    assert form2.initial['privacy_type'] == 'public'

    data2 = form2.initial.copy()
    data2['privacy_type'] = 'private'
    data2.setdefault('timezone', 'UTC')
    data2.setdefault('locale', 'en')
    data2.setdefault('locales', ['en'])
    bound_form2 = EventCommonSettingsForm(data=data2, obj=event)
    assert bound_form2.is_valid(), bound_form2.errors
    bound_form2.save()

    event.refresh_from_db()
    assert event.live is True
    assert event.tickets_published is True
    assert event.is_public is False
    assert event.settings.get('meta_noindex', as_type=bool) is True


@pytest.mark.django_db
@scopes_disabled()
def test_event_update_form_drops_is_public_for_meetups(meetup_event):
    """EventUpdateForm should not include is_public for meetups so saving it does not overwrite privacy."""
    meetup_event.is_public = True
    meetup_event.save(update_fields=['is_public'])

    form = EventUpdateForm(instance=meetup_event)
    assert 'is_public' not in form.fields


@pytest.mark.django_db
@scopes_disabled()
def test_presale_shows_registration_closed_when_quota_full(meetup_event, rf):
    """Presale context reports rsvp_registration_closed=True when capacity is reached."""
    product, quota = get_rsvp_product_and_quota(meetup_event)
    quota.size = 1
    quota.save(update_fields=['size'])

    request = rf.get(f'/{meetup_event.slug}/')
    request.event = meetup_event
    request.user = AnonymousUser()
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()

    view = EventIndex()
    view.request = request
    ctx = view.get_meetup_context()
    assert ctx['rsvp_registration_closed'] is False

    create_paid_order(meetup_event, product, email='first@example.com')

    ctx_after = view.get_meetup_context()
    assert ctx_after['rsvp_registration_closed'] is True


@pytest.mark.django_db
@scopes_disabled()
def test_create_rsvp_order_blocks_when_quota_exhausted(meetup_event, rf):
    """Free RSVP is blocked and redirects when quota is exhausted."""
    product, quota = get_rsvp_product_and_quota(meetup_event)
    quota.size = 1
    quota.save(update_fields=['size'])

    create_paid_order(meetup_event, product, email='first@example.com')

    request = rf.post(
        f'/{meetup_event.slug}/rsvp',
        data={'attendee_name': 'Second Attendee', 'attendee_email': 'second@example.com'},
    )
    request.event = meetup_event
    request.LANGUAGE_CODE = 'en'
    request.user = AnonymousUser()
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    setattr(request, '_messages', FallbackStorage(request))

    view = MeetupRsvpView()
    response = view.post(request)
    assert response.status_code == 302
    assert Order.objects.filter(event=meetup_event, email='second@example.com').exists() is False


@pytest.mark.django_db
@scopes_disabled()
def test_authenticated_user_authz_by_email_only(meetup_event, rf, user):
    """Authenticated users must match order by email only; cannot hijack session order code."""
    product, quota = get_rsvp_product_and_quota(meetup_event)

    victim_order = create_paid_order(
        meetup_event,
        product,
        email='other@example.com',
        name='Other User',
        code='VICTIM123',
    )

    request = rf.get(f'/{meetup_event.slug}/video')
    request.event = meetup_event
    request.user = user
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session[MEETUP_RSVP_SESSION_KEY.format(meetup_event.pk)] = victim_order.code
    request.session.save()

    view = JoinOnlineVideoView()
    view.request = request
    allowed, _, order = view.validate_access(request)
    assert allowed is False
    assert order is None

    own_order = create_paid_order(
        meetup_event,
        product,
        email=user.email,
        name=user.fullname,
        code='USER123',
    )
    allowed, _, order = view.validate_access(request)
    assert allowed is True
    assert order.code == own_order.code


@pytest.mark.django_db
@scopes_disabled()
def test_anonymous_guest_authz_by_session_order_code(meetup_event, rf):
    """Anonymous guest users authorize strictly via their session order code."""
    product, quota = get_rsvp_product_and_quota(meetup_event)

    guest_order = create_paid_order(
        meetup_event,
        product,
        email='guest@example.com',
        name='Guest User',
        code='GUEST123',
    )

    request = rf.get(f'/{meetup_event.slug}/video')
    request.event = meetup_event
    request.user = AnonymousUser()
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)

    view = JoinOnlineVideoView()
    view.request = request
    allowed, _, order = view.validate_access(request)
    assert allowed is False

    request.session[MEETUP_RSVP_SESSION_KEY.format(meetup_event.pk)] = guest_order.code
    request.session.save()
    allowed, _, order = view.validate_access(request)
    assert allowed is True
    assert order.code == guest_order.code


@pytest.mark.django_db
@scopes_disabled()
def test_provision_meetup_event_with_registration_fee(meetup_event):
    """Provisioning meetup event sets product price and Stripe settings."""
    provision_meetup_event(
        meetup_event,
        registration_fee=Decimal('15.50'),
        payment_stripe_publishable_key='pk_test_123',
        payment_stripe_secret_key='sk_test_456',
        payment_stripe_merchant_country='US',
    )
    product, quota = get_rsvp_product_and_quota(meetup_event)
    assert product.default_price == Decimal('15.50')
    assert meetup_event.settings.get('payment_stripe__enabled', as_type=bool) is True
    assert meetup_event.settings.get('payment_stripe_publishable_key') == 'pk_test_123'
    assert meetup_event.settings.get('payment_stripe_secret_key') == 'sk_test_456'
    assert meetup_event.settings.get('payment_stripe_merchant_country') == 'US'


@pytest.mark.django_db
@scopes_disabled()
def test_settings_form_preserves_secret_key_when_empty_submitted(meetup_event):
    """EventCommonSettingsForm preserves existing Stripe secret key on empty submission."""
    meetup_event.settings.set('payment_stripe_secret_key', 'sk_test_existing_secret')
    meetup_event.settings.set('payment_stripe_publishable_key', 'pk_test_existing_pub')
    meetup_event.settings.set('payment_stripe_merchant_country', 'US')

    form = EventCommonSettingsForm(obj=meetup_event)
    data = form.initial.copy()
    data['registration_fee'] = Decimal('10.00')
    data['payment_stripe_publishable_key'] = 'pk_test_existing_pub'
    data['payment_stripe_secret_key'] = ''  # PasswordInput submitted empty
    data['payment_stripe_merchant_country'] = 'US'
    data.setdefault('timezone', 'UTC')
    data.setdefault('locale', 'en')
    data.setdefault('locales', ['en'])

    bound_form = EventCommonSettingsForm(data=data, obj=meetup_event)
    assert bound_form.is_valid(), bound_form.errors
    bound_form.save()

    assert meetup_event.settings.get('payment_stripe_secret_key') == 'sk_test_existing_secret'


@pytest.mark.django_db
@scopes_disabled()
def test_stripe_payment_provider_is_allowed_only_for_meetups(meetup_event, organizer, rf):
    """StripePaymentProvider is allowed for meetup events and blocked for standard events."""
    meetup_event.settings.set('payment_stripe__enabled', True)
    meetup_event.settings.set('payment_stripe_secret_key', 'sk_test_123')

    req = rf.get('/')
    SessionMiddleware(lambda r: None).process_request(req)
    req.session.save()
    req.event = meetup_event
    req.resolver_match = None

    meetup_provider = StripePaymentProvider(meetup_event)
    assert meetup_provider.is_enabled is True
    assert meetup_provider.is_allowed(req) is True

    standard_event = Event.objects.create(
        organizer=organizer,
        name='Standard Event Test',
        slug='standard-event-test',
        date_from=timezone.now() + timedelta(days=10),
        date_to=timezone.now() + timedelta(days=10, hours=2),
        currency='USD',
        locale='en',
    )
    standard_event.settings.set('payment_stripe__enabled', True)
    standard_event.settings.set('payment_stripe_secret_key', 'sk_test_123')

    standard_req = rf.get('/')
    SessionMiddleware(lambda r: None).process_request(standard_req)
    standard_req.session.save()
    standard_req.event = standard_event
    standard_req.resolver_match = None

    standard_provider = StripePaymentProvider(standard_event)
    assert standard_provider.is_enabled is True
    assert standard_provider.is_allowed(standard_req) is False


@pytest.mark.django_db
@scopes_disabled()
def test_private_meetup_guest_rsvp_via_direct_link_creates_order(organizer, rf):
    now = timezone.now()
    event = Event.objects.create(
        organizer=organizer,
        name='Private Meetup Testing',
        slug='private-meetup-testing',
        date_from=now + timedelta(days=10),
        date_to=now + timedelta(days=10, hours=2),
        currency='USD',
        locale='en',
    )
    provision_meetup_event(event, is_private=True)
    assert event.live is True
    assert event.tickets_published is True
    assert event.is_public is False
    assert event.settings.get('meta_noindex', as_type=bool) is True
    event.settings.set('require_registered_account_for_tickets', False)

    request = rf.post(
        f'/{event.slug}/rsvp',
        data={'attendee_name': 'Guest NonMember', 'attendee_email': 'guest@test.org'},
    )
    request.event = event
    request.user = AnonymousUser()
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    setattr(request, '_messages', FallbackStorage(request))

    view = MeetupRsvpView()
    view.setup(request)
    response = view.post(request)
    assert response.status_code == 302

    order = event.orders.filter(email='guest@test.org').first()
    assert order is not None


@pytest.mark.django_db
@scopes_disabled()
def test_paid_rsvp_success_creates_paid_order(meetup_event, rf):
    """Paid RSVP successfully charges Stripe, confirms payment, and marks order paid."""
    product, quota = get_rsvp_product_and_quota(meetup_event)
    product.default_price = Decimal('25.00')
    product.save(update_fields=['default_price'])

    meetup_event.settings.set('payment_stripe__enabled', True)
    meetup_event.settings.set('payment_stripe_publishable_key', 'pk_test_123')
    meetup_event.settings.set('payment_stripe_secret_key', 'sk_test_123')
    meetup_event.settings.set('require_registered_account_for_tickets', False)

    req = rf.post(
        f'/{meetup_event.slug}/rsvp',
        data={
            'attendee_name': 'Paid Attendee',
            'attendee_email': 'paid_attendee@example.com',
            'stripe_token': 'tok_visa',
        },
    )
    req.event = meetup_event
    req.LANGUAGE_CODE = 'en'
    req.user = AnonymousUser()
    SessionMiddleware(lambda r: None).process_request(req)
    req.session.save()
    setattr(req, '_messages', FallbackStorage(req))

    mock_intent = MagicMock()
    mock_intent.id = 'pi_test_paid_123'
    mock_intent.status = 'succeeded'

    with patch('stripe.PaymentIntent.create', return_value=mock_intent) as mock_create:
        view = MeetupRsvpView()
        response = view.post(req)
        assert response.status_code == 302
        mock_create.assert_called_once()

    order = Order.objects.get(event=meetup_event, email='paid_attendee@example.com')
    assert order.status == Order.STATUS_PAID
    assert order.total == Decimal('25.00')

    payment = order.payments.first()
    assert payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED
    assert payment.provider == 'stripe'


@pytest.mark.django_db
@scopes_disabled()
def test_paid_rsvp_card_error_cancels_order_and_sets_payment_failed(meetup_event, rf):
    """CardError during Stripe payment intent cancels order and marks payment as FAILED."""
    product, quota = get_rsvp_product_and_quota(meetup_event)
    product.default_price = Decimal('15.00')
    product.save(update_fields=['default_price'])

    meetup_event.settings.set('payment_stripe__enabled', True)
    meetup_event.settings.set('payment_stripe_publishable_key', 'pk_test_123')
    meetup_event.settings.set('payment_stripe_secret_key', 'sk_test_123')
    meetup_event.settings.set('require_registered_account_for_tickets', False)

    req = rf.post(
        f'/{meetup_event.slug}/rsvp',
        data={
            'attendee_name': 'Declined User',
            'attendee_email': 'declined@example.com',
            'stripe_token': 'tok_declined',
        },
    )
    req.event = meetup_event
    req.LANGUAGE_CODE = 'en'
    req.user = AnonymousUser()
    SessionMiddleware(lambda r: None).process_request(req)
    req.session.save()
    setattr(req, '_messages', FallbackStorage(req))

    card_err = stripe.error.CardError(
        message='Your card was declined.',
        param='card_number',
        code='card_declined',
    )

    with patch('stripe.PaymentIntent.create', side_effect=card_err):
        view = MeetupRsvpView()
        response = view.post(req)
        assert response.status_code == 302

    order = Order.objects.get(event=meetup_event, email='declined@example.com')
    assert order.status == Order.STATUS_CANCELED

    payment = order.payments.first()
    assert payment.state == OrderPayment.PAYMENT_STATE_FAILED


@pytest.mark.django_db
@scopes_disabled()
def test_private_meetup_excluded_from_organizer_public_listing(organizer):
    now = timezone.now()
    public_event = Event.objects.create(
        organizer=organizer,
        name='Public Meetup Listing',
        slug='public-meetup-listing',
        date_from=now + timedelta(days=10),
        date_to=now + timedelta(days=10, hours=2),
        currency='USD',
        locale='en',
    )
    provision_meetup_event(public_event, is_private=False)

    private_event = Event.objects.create(
        organizer=organizer,
        name='Private Meetup Hidden',
        slug='private-meetup-hidden',
        date_from=now + timedelta(days=10),
        date_to=now + timedelta(days=10, hours=2),
        currency='USD',
        locale='en',
    )
    provision_meetup_event(private_event, is_private=True)

    public_listed = organizer.events.filter(is_public=True, live=True)
    assert public_event in public_listed
    assert private_event not in public_listed
