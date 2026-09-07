import json
import logging
import secrets
from decimal import Decimal

import stripe
from django import forms
from django.conf import settings as django_settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views import View
from django_scopes import scope

from eventyay.base.meetup import get_rsvp_product_and_quota, is_meetup_event
from eventyay.base.models import Quota
from eventyay.base.models.orders import Order, OrderPayment, OrderPosition
from eventyay.base.templatetags.money import money_filter
from eventyay.multidomain.urlreverse import eventreverse
from eventyay.presale.views import EventViewMixin

logger = logging.getLogger(__name__)

MEETUP_RSVP_SESSION_KEY = 'meetup_rsvp_registered_{}'
RSVP_ORDER_STATUSES = (Order.STATUS_PAID,)


class GuestRsvpForm(forms.Form):
    attendee_name = forms.CharField(
        label=_('Your name'),
        max_length=255,
        error_messages={'required': _('Your name is required.')},
    )
    attendee_email = forms.EmailField(
        label=_('Your email'),
        error_messages={
            'required': _('A valid email address is required.'),
            'invalid': _('A valid email address is required.'),
        },
    )


def has_rsvp_order(event, email) -> bool:
    if not email:
        return False
    with scope(organizer=event.organizer):
        return event.orders.filter(email__iexact=email, status__in=RSVP_ORDER_STATUSES).exists()


class MeetupRsvpView(EventViewMixin, View):

    def get(self, request, *args, **kwargs):
        return self._redirect_to_index(request)

    def post(self, request, *args, **kwargs):
        if not is_meetup_event(request.event):
            raise Http404

        if not request.event.user_can_view_tickets(request.user, request=request):
            raise PermissionDenied(_('Registration is currently not available.'))

        product, quota = get_rsvp_product_and_quota(request.event)
        if product is None or quota is None:
            raise Http404

        if not request.event.presale_is_running:
            messages.error(request, _('Registration for this event is not currently open.'))
            return self._redirect_to_index(request)

        if request.user.is_authenticated:
            email = request.user.email
            name = getattr(request.user, 'fullname', None) or getattr(request.user, 'name', None) or email
        else:
            if request.event.settings.require_registered_account_for_tickets:
                messages.error(request, _('Please log in to register for this event.'))
                return self._redirect_to_index(request)

            form = GuestRsvpForm(data=request.POST)
            if not form.is_valid():
                return self._render_index_with_form_errors(request, form)
            email = form.cleaned_data['attendee_email']
            name = form.cleaned_data['attendee_name']

        if has_rsvp_order(request.event, email):
            messages.info(request, _('You are already registered for this event.'))
            return self._redirect_to_index(request)

        price = product.default_price or Decimal('0.00')
        is_paid = price > Decimal('0.00')

        if is_paid:
            return self._process_paid_rsvp(request, product, email, name, price)
        return self._process_free_rsvp(request, product, email, name)

    def _redirect_to_index(self, request):
        return redirect(eventreverse(request.event, 'presale:event.index'))

    def _process_free_rsvp(self, request, product, email, name):
        with transaction.atomic():
            _prod, rsvp_quota = get_rsvp_product_and_quota(request.event)
            with scope(organizer=request.event.organizer):
                if rsvp_quota is not None:
                    quota = Quota.objects.select_for_update().get(pk=rsvp_quota.pk)
                    avail, count = quota.availability()
                    if avail != Quota.AVAILABILITY_OK:
                        messages.error(request, _('Sorry, this event is already full.'))
                        return self._redirect_to_index(request)

                order = Order(
                    status=Order.STATUS_PENDING,
                    event=request.event,
                    email=email,
                    locale=getattr(request, 'LANGUAGE_CODE', 'en'),
                    total=Decimal('0.00'),
                    datetime=now(),
                    sales_channel='web',
                    require_approval=False,
                    testmode=request.event.testmode,
                    meta_info='{}',
                )
                order.set_expires(now(), [])
                order.save()

                position = OrderPosition(
                    order=order,
                    product=product,
                    price=Decimal('0.00'),
                    tax_rate=Decimal('0.00'),
                    tax_value=Decimal('0.00'),
                    positionid=1,
                    attendee_name_parts={'_legacy': name},
                    attendee_email=email,
                )
                position.secret = secrets.token_hex(16)
                position.pseudonymization_id = secrets.token_hex(8)
                position.save()

                payment = order.payments.create(
                    state=OrderPayment.PAYMENT_STATE_CREATED,
                    provider='free',
                    amount=Decimal('0.00'),
                )
                payment.confirm(send_mail=True, lock=False)
                order.refresh_from_db()

        request.session[MEETUP_RSVP_SESSION_KEY.format(request.event.pk)] = order.code
        messages.success(request, _("You're registered! We look forward to seeing you."))
        return self._redirect_to_index(request)

    def _process_paid_rsvp(self, request, product, email, name, price):
        stripe_token = (request.POST.get('stripe_token') or '').strip()

        if not stripe_token:
            messages.error(request, _('Please complete the card payment details to register.'))
            return self._redirect_to_index(request)

        stripe_enabled = request.event.settings.get('payment_stripe__enabled', as_type=bool, default=False)
        publishable_key = request.event.settings.get('payment_stripe_publishable_key')
        secret_key = request.event.settings.get('payment_stripe_secret_key')
        if not stripe_enabled or not publishable_key or not secret_key:
            messages.error(request, _('Payment is currently unavailable because the organizer payment settings are incomplete.'))
            return self._redirect_to_index(request)

        with transaction.atomic():
            _prod, rsvp_quota = get_rsvp_product_and_quota(request.event)
            with scope(organizer=request.event.organizer):
                if rsvp_quota is not None:
                    quota = Quota.objects.select_for_update().get(pk=rsvp_quota.pk)
                    avail, count = quota.availability()
                    if avail != Quota.AVAILABILITY_OK:
                        messages.error(request, _('Sorry, this event is already full.'))
                        return self._redirect_to_index(request)

                order = Order(
                    status=Order.STATUS_PENDING,
                    event=request.event,
                    email=email,
                    locale=getattr(request, 'LANGUAGE_CODE', 'en'),
                    total=price,
                    datetime=now(),
                    sales_channel='web',
                    require_approval=False,
                    testmode=request.event.testmode,
                    meta_info='{}',
                )
                order.set_expires(now(), [])
                order.save()

                position = OrderPosition(
                    order=order,
                    product=product,
                    price=price,
                    tax_rate=Decimal('0.00'),
                    tax_value=Decimal('0.00'),
                    positionid=1,
                    attendee_name_parts={'_legacy': name},
                    attendee_email=email,
                )
                position.secret = secrets.token_hex(16)
                position.pseudonymization_id = secrets.token_hex(8)
                position.save()

                payment = order.payments.create(
                    state=OrderPayment.PAYMENT_STATE_CREATED,
                    provider='stripe',
                    amount=price,
                )

        try:
            places = getattr(django_settings, 'CURRENCY_PLACES', {}).get(request.event.currency, 2)
            stripe_amount = int(round(order.total * (10 ** places)))

            params = {
                'amount': stripe_amount,
                'currency': request.event.currency.lower(),
                'confirm': True,
                'automatic_payment_methods': {
                    'enabled': True,
                    'allow_redirects': 'never',
                },
                'description': f'Meetup RSVP {order.code} - {request.event.name}',
                'metadata': {
                    'order_code': order.code,
                    'event_slug': request.event.slug,
                },
                'api_key': secret_key,
            }
            if stripe_token.startswith('tok_'):
                params['payment_method_data'] = {'type': 'card', 'card': {'token': stripe_token}}
            else:
                params['payment_method'] = stripe_token

            intent = stripe.PaymentIntent.create(**params)
            if getattr(intent, 'status', '') != 'succeeded':
                with scope(organizer=request.event.organizer):
                    order.status = Order.STATUS_CANCELED
                    order.save(update_fields=['status'])
                    payment.state = OrderPayment.PAYMENT_STATE_FAILED
                    payment.save(update_fields=['state'])
                messages.error(request, _('Payment was not completed successfully. Please try again.'))
                return self._redirect_to_index(request)

            with scope(organizer=request.event.organizer):
                payment.info = json.dumps({'payment_intent_id': intent.id, 'status': intent.status})
                payment.save(update_fields=['info'])
                try:
                    payment.confirm(send_mail=True, lock=False)
                    order.refresh_from_db()
                except Exception as confirm_exc:
                    logger.exception(f'Error confirming payment for order {order.code} after intent {intent.id}: {confirm_exc}')
                    try:
                        stripe.Refund.create(payment_intent=intent.id, api_key=secret_key)
                    except Exception as refund_exc:
                        logger.exception(f'Failed to auto-refund intent {intent.id} for order {order.code}: {refund_exc}')
                    order.status = Order.STATUS_CANCELED
                    order.save(update_fields=['status'])
                    payment.state = OrderPayment.PAYMENT_STATE_FAILED
                    payment.save(update_fields=['state'])
                    messages.error(request, _('Payment could not be completed. Any charge has been automatically refunded.'))
                    return self._redirect_to_index(request)
        except stripe.error.CardError as e:
            with scope(organizer=request.event.organizer):
                order.status = Order.STATUS_CANCELED
                order.save(update_fields=['status'])
                payment.state = OrderPayment.PAYMENT_STATE_FAILED
                payment.save(update_fields=['state'])
            messages.error(request, _('Payment failed: ') + str(e.user_message or e))
            return self._redirect_to_index(request)
        except stripe.error.StripeError as e:
            logger.warning(f'Stripe error during meetup RSVP for order {order.code}: {e}')
            with scope(organizer=request.event.organizer):
                order.status = Order.STATUS_CANCELED
                order.save(update_fields=['status'])
                payment.state = OrderPayment.PAYMENT_STATE_FAILED
                payment.save(update_fields=['state'])
            messages.error(request, _('Payment processing error: ') + str(e.user_message or e))
            return self._redirect_to_index(request)
        except Exception as e:
            logger.exception(f'Unexpected error during meetup RSVP for order {order.code}: {e}')
            with scope(organizer=request.event.organizer):
                order.status = Order.STATUS_CANCELED
                order.save(update_fields=['status'])
                payment.state = OrderPayment.PAYMENT_STATE_FAILED
                payment.save(update_fields=['state'])
            messages.error(request, _('An unexpected error occurred while processing your payment. Please try again.'))
            return self._redirect_to_index(request)

        request.session[MEETUP_RSVP_SESSION_KEY.format(request.event.pk)] = order.code
        messages.success(
            request,
            _("You're registered! Your payment of {amount} has been received.").format(
                amount=money_filter(order.total, request.event.currency)
            ),
        )
        return self._redirect_to_index(request)

    def _render_index_with_form_errors(self, request, form):
        from eventyay.presale.views.event import EventIndex

        request._rsvp_guest_form = form
        view = EventIndex()
        view.setup(request, *self.args, **self.kwargs)
        return view.get(request, *self.args, **self.kwargs)
