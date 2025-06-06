import inspect
import json
import mimetypes
import os
import re
from collections import OrderedDict
from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.files import File
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Sum
from django.http import (
    FileResponse,
    Http404,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView, View

from pretix.base.models import (
    CachedTicket,
    GiftCard,
    Invoice,
    Order,
    OrderPosition,
    Quota,
    TaxRule,
)
from pretix.base.models.orders import (
    CachedCombinedTicket,
    InvoiceAddress,
    OrderFee,
    OrderPayment,
    OrderRefund,
    QuestionAnswer,
)
from pretix.base.payment import PaymentException
from pretix.base.services.invoices import (
    generate_cancellation,
    generate_invoice,
    invoice_pdf,
    invoice_pdf_task,
    invoice_qualified,
)
from pretix.base.services.mail import SendMailException
from pretix.base.services.orders import (
    OrderChangeManager,
    OrderError,
    cancel_order,
    change_payment_provider,
)
from pretix.base.services.pricing import get_price
from pretix.base.services.tickets import generate, invalidate_cache
from pretix.base.signals import (
    allow_ticket_download,
    order_modified,
    register_ticket_outputs,
)
from pretix.base.templatetags.money import money_filter
from pretix.base.views.mixins import OrderQuestionsViewMixin
from pretix.base.views.tasks import AsyncAction
from pretix.helpers.safedownload import check_token
from pretix.multidomain.urlreverse import build_absolute_uri, eventreverse
from pretix.presale.forms.checkout import InvoiceAddressForm, QuestionsForm
from pretix.presale.forms.order import OrderPositionChangeForm
from pretix.presale.signals import question_form_fields_overrides
from pretix.presale.views import (
    CartMixin,
    EventViewMixin,
    iframe_entry_view_wrapper,
)
from pretix.presale.views.robots import NoSearchIndexViewMixin


class OrderDetailMixin(NoSearchIndexViewMixin):
    @cached_property
    def order(self):
        order = self.request.event.orders.filter(code=self.kwargs['order']).select_related('event').first()
        if order:
            if order.secret.lower() == self.kwargs['secret'].lower():
                return order
            else:
                return None
        else:
            # Do a comparison as well to harden timing attacks
            if 'abcdefghijklmnopq'.lower() == self.kwargs['secret'].lower():
                return None
            else:
                return None

    def get_order_url(self):
        return eventreverse(
            self.request.event,
            'presale:event.order',
            kwargs={'order': self.order.code, 'secret': self.order.secret},
        )


class OrderPositionDetailMixin(NoSearchIndexViewMixin):
    @cached_property
    def position(self):
        p = (
            OrderPosition.objects.filter(
                order__event=self.request.event,
                addon_to__isnull=True,
                order__code=self.kwargs['order'],
                positionid=self.kwargs['position'],
            )
            .select_related('order', 'order__event')
            .first()
        )
        if p:
            if p.web_secret.lower() == self.kwargs['secret'].lower():
                return p
            else:
                return None
        else:
            # Do a comparison as well to harden timing attacks
            if 'abcdefghijklmnopq'.lower() == self.kwargs['secret'].lower():
                return None
            else:
                return None

    @cached_property
    def order(self):
        return self.position.order if self.position else None

    def get_position_url(self):
        return eventreverse(
            self.request.event,
            'presale:event.order.position',
            kwargs={
                'order': self.order.code,
                'secret': self.position.web_secret,
                'position': self.position.positionid,
            },
        )


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderOpen(EventViewMixin, OrderDetailMixin, View):
    def get(self, request, *args, **kwargs):
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        if kwargs.get('hash') == self.order.email_confirm_hash():
            if not self.order.email_known_to_work:
                self.order.log_action('pretix.event.order.contact.confirmed')
                self.order.email_known_to_work = True
                self.order.save(update_fields=['email_known_to_work'])
        return redirect(self.get_order_url())


class TicketPageMixin:
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        ctx['order'] = self.order

        can_download = all([r for rr, r in allow_ticket_download.send(self.request.event, order=self.order)])
        if self.request.event.settings.ticket_download_date:
            ctx['ticket_download_date'] = self.order.ticket_download_date
        can_download = can_download and self.order.ticket_download_available and list(self.order.positions_with_tickets)
        ctx['download_email_required'] = can_download and (
            self.request.event.settings.ticket_download_require_validated_email
            and self.order.sales_channel == 'web'
            and not self.order.email_known_to_work
        )
        ctx['can_download'] = can_download and not ctx['download_email_required']

        ctx['download_buttons'] = self.download_buttons

        ctx['backend_user'] = self.request.user.is_authenticated and self.request.user.has_event_permission(
            self.request.organizer,
            self.request.event,
            'can_view_orders',
            request=self.request,
        )
        return ctx


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderDetails(EventViewMixin, OrderDetailMixin, CartMixin, TicketPageMixin, TemplateView):
    template_name = 'pretixpresale/event/order.html'

    def get(self, request, *args, **kwargs):
        self.kwargs = kwargs
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        return super().get(request, *args, **kwargs)

    @cached_property
    def download_buttons(self):
        buttons = []

        responses = register_ticket_outputs.send(self.request.event)
        for receiver, response in responses:
            provider = response(self.request.event)
            if not provider.is_enabled:
                continue
            buttons.append(
                {
                    'text': provider.download_button_text or 'Download',
                    'multi_text': provider.multi_download_button_text or 'Download',
                    'long_text': provider.long_download_button_text or 'Download',
                    'icon': provider.download_button_icon or 'fa-download',
                    'identifier': provider.identifier,
                    'multi': provider.multi_download_enabled,
                    'javascript_required': provider.javascript_required,
                }
            )
        return buttons

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cart'] = self.get_cart(
            answers=True,
            downloads=ctx['can_download'],
            queryset=self.order.positions.prefetch_related('issued_gift_cards').select_related('tax_rule'),
            order=self.order,
        )
        ctx['tickets_with_download'] = [p for p in ctx['cart']['positions'] if p.generate_ticket]
        ctx['can_download_multi'] = any([b['multi'] for b in self.download_buttons]) and (
            [p.generate_ticket for p in ctx['cart']['positions']].count(True) > 1
        )
        ctx['invoices'] = list(self.order.invoices.all())
        ctx['can_generate_invoice'] = can_generate_invoice(self.request.event, self.order, ignore_payments=True)
        if ctx['can_generate_invoice']:
            if (
                not self.order.payments.exclude(
                    state__in=[
                        OrderPayment.PAYMENT_STATE_CANCELED,
                        OrderPayment.PAYMENT_STATE_FAILED,
                    ]
                ).exists()
                and self.order.status == Order.STATUS_PENDING
            ):
                ctx['generate_invoice_requires'] = 'payment'
        ctx['url'] = build_absolute_uri(
            self.request.event,
            'presale:event.order',
            kwargs={'order': self.order.code, 'secret': self.order.secret},
        )
        ctx['invoice_address_asked'] = self.request.event.settings.invoice_address_asked and (
            self.order.total != Decimal('0.00') or not self.request.event.settings.invoice_address_not_asked_free
        )

        if self.order.status == Order.STATUS_PENDING:
            ctx['pending_sum'] = self.order.pending_sum
            ctx['payment_sum_neg'] = ctx['pending_sum'] - self.order.total

            lp = self.order.payments.last()
            ctx['can_pay'] = False

            for provider in self.request.event.get_payment_providers().values():
                if provider.is_enabled and provider.order_change_allowed(self.order):
                    ctx['can_pay'] = True
                    break

            if lp and lp.state not in (
                OrderPayment.PAYMENT_STATE_CONFIRMED,
                OrderPayment.PAYMENT_STATE_REFUNDED,
                OrderPayment.PAYMENT_STATE_CANCELED,
            ):
                ctx['last_payment'] = lp

                pp = lp.payment_provider
                ctx['last_payment_info'] = pp.payment_pending_render(self.request, ctx['last_payment'])

                if lp.state == OrderPayment.PAYMENT_STATE_PENDING and not pp.abort_pending_allowed:
                    ctx['can_pay'] = False

            ctx['can_pay'] = ctx['can_pay'] and self.order._can_be_paid() is True

        elif self.order.status == Order.STATUS_PAID:
            ctx['can_pay'] = False

        ctx['refunds'] = self.order.refunds.filter(
            state__in=(
                OrderRefund.REFUND_STATE_DONE,
                OrderRefund.REFUND_STATE_TRANSIT,
                OrderRefund.REFUND_STATE_CREATED,
            )
        ).exclude(provider__in=('offsetting', 'reseller', 'boxoffice', 'manual'))
        ctx['user_change_allowed'] = self.order.user_change_allowed
        ctx['user_cancel_allowed'] = self.order.user_cancel_allowed
        for r in ctx['refunds']:
            if r.provider == 'giftcard':
                gc = GiftCard.objects.get(pk=r.info_data.get('gift_card'))
                r.giftcard = gc

        return ctx


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderPositionDetails(EventViewMixin, OrderPositionDetailMixin, CartMixin, TicketPageMixin, TemplateView):
    template_name = 'pretixpresale/event/position.html'

    def get(self, request, *args, **kwargs):
        self.kwargs = kwargs
        if not self.position:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        return super().get(request, *args, **kwargs)

    @cached_property
    def download_buttons(self):
        buttons = []

        responses = register_ticket_outputs.send(self.request.event)
        for receiver, response in responses:
            provider = response(self.request.event)
            if not provider.is_enabled:
                continue
            buttons.append(
                {
                    'text': provider.download_button_text or 'Download',
                    'icon': provider.download_button_icon or 'fa-download',
                    'identifier': provider.identifier,
                    'multi': provider.multi_download_enabled,
                    'multi_text': provider.multi_download_button_text or 'Download',
                    'long_text': provider.long_download_button_text or 'Download',
                    'javascript_required': provider.javascript_required,
                }
            )
        return buttons

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['can_download_multi'] = False
        ctx['position'] = self.position
        ctx['cart'] = self.get_cart(
            answers=True,
            downloads=ctx['can_download'],
            queryset=self.order.positions.select_related('tax_rule').filter(
                Q(pk=self.position.pk) | Q(addon_to__id=self.position.pk)
            ),
            order=self.order,
        )
        ctx['tickets_with_download'] = [p for p in ctx['cart']['positions'] if p.generate_ticket]
        return ctx


@method_decorator(xframe_options_exempt, 'dispatch')
@method_decorator(iframe_entry_view_wrapper, 'dispatch')
class OrderPaymentStart(EventViewMixin, OrderDetailMixin, TemplateView):
    """
    This is used if a payment is retried or the payment method is changed. It shows the payment
    provider's form that asks for payment details (e.g. CC number).
    """

    template_name = 'pretixpresale/event/order_pay.html'

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        if (
            self.order.status not in (Order.STATUS_PENDING, Order.STATUS_EXPIRED)
            or self.payment.state != OrderPayment.PAYMENT_STATE_CREATED
            or not self.payment.payment_provider.is_enabled
            or self.order._can_be_paid() is not True
        ):
            messages.error(request, _('The payment for this order cannot be continued.'))
            return redirect(self.get_order_url())

        term_last = self.order.payment_term_last
        if term_last and now() > term_last:
            messages.error(request, _('The payment is too late to be accepted.'))
            return redirect(self.get_order_url())
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        resp = self.payment.payment_provider.payment_prepare(request, self.payment)
        if 'payment_change_{}'.format(self.order.pk) in request.session:
            del request.session['payment_change_{}'.format(self.order.pk)]
        if isinstance(resp, str):
            return redirect(resp)
        elif resp is True:
            return redirect(self.get_confirm_url())
        else:
            return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = self.order
        ctx['form'] = self.form
        ctx['provider'] = self.payment.payment_provider
        return ctx

    @cached_property
    def form(self):
        if 'total' in inspect.signature(self.payment.payment_provider.payment_form_render).parameters:
            return self.payment.payment_provider.payment_form_render(self.request, self.payment.amount)
        else:
            return self.payment.payment_provider.payment_form_render(self.request)

    @cached_property
    def payment(self):
        return get_object_or_404(self.order.payments, pk=self.kwargs['payment'])

    def get_confirm_url(self):
        return eventreverse(
            self.request.event,
            'presale:event.order.pay.confirm',
            kwargs={
                'order': self.order.code,
                'secret': self.order.secret,
                'payment': self.payment.pk,
            },
        )


@method_decorator(xframe_options_exempt, 'dispatch')
@method_decorator(iframe_entry_view_wrapper, 'dispatch')
class OrderPaymentConfirm(EventViewMixin, OrderDetailMixin, TemplateView):
    """
    This is used if a payment is retried or the payment method is changed. It is shown after the
    payment details have been entered and allows the user to confirm and review the details. On
    submitting this view, the payment is performed.
    """

    template_name = 'pretixpresale/event/order_pay_confirm.html'

    @cached_property
    def payment(self):
        return get_object_or_404(self.order.payments, pk=self.kwargs['payment'])

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        if self.payment.state != OrderPayment.PAYMENT_STATE_CREATED or not self.order._can_be_paid():
            messages.error(request, _('The payment for this order cannot be continued.'))
            return redirect(self.get_order_url())
        if (
            not self.payment.payment_provider.payment_is_valid_session(request)
            or not self.payment.payment_provider.is_enabled
        ):
            messages.error(request, _('The payment information you entered was incomplete.'))
            return redirect(self.get_payment_url())

        term_last = self.order.payment_term_last
        if term_last and now() > term_last:
            messages.error(request, _('The payment is too late to be accepted.'))
            return redirect(self.get_order_url())

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            if not self.order.invoices.exists() and invoice_qualified(self.order):
                if self.request.event.settings.get('invoice_generate') == 'True' or (
                    self.request.event.settings.get('invoice_generate') == 'paid'
                    and self.payment.payment_provider.requires_invoice_immediately
                ):
                    i = generate_invoice(self.order)
                    self.order.log_action('pretix.event.order.invoice.generated', data={'invoice': i.pk})
                    messages.success(self.request, _('An invoice has been generated.'))
            resp = self.payment.payment_provider.execute_payment(request, self.payment)
        except PaymentException as e:
            messages.error(request, str(e))
            return redirect(self.get_order_url())
        if 'payment_change_{}'.format(self.order.pk) in request.session:
            del request.session['payment_change_{}'.format(self.order.pk)]
        return redirect(resp or self.get_order_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = self.order
        ctx['payment'] = self.payment
        if 'order' in inspect.signature(self.payment.payment_provider.checkout_confirm_render).parameters:
            ctx['payment_info'] = self.payment.payment_provider.checkout_confirm_render(self.request, order=self.order)
        else:
            ctx['payment_info'] = self.payment.payment_provider.checkout_confirm_render(self.request)
        ctx['payment_provider'] = self.payment.payment_provider
        return ctx

    def get_payment_url(self):
        return eventreverse(
            self.request.event,
            'presale:event.order.pay',
            kwargs={
                'order': self.order.code,
                'secret': self.order.secret,
                'payment': self.payment.pk,
            },
        )


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderPaymentComplete(EventViewMixin, OrderDetailMixin, View):
    """
    This is used for the first try of a payment. This means the user just entered payment
    details and confirmed them during the order process and we don't need to show them again,
    we just need to perform the payment.
    """

    @cached_property
    def payment(self):
        return get_object_or_404(self.order.payments, pk=self.kwargs['payment'])

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        if self.payment.state != OrderPayment.PAYMENT_STATE_CREATED or not self.order._can_be_paid():
            messages.error(request, _('The payment for this order cannot be continued.'))
            return redirect(self.get_order_url())
        if (
            not self.payment.payment_provider.payment_is_valid_session(request)
            or not self.payment.payment_provider.is_enabled
        ):
            messages.error(request, _('The payment information you entered was incomplete.'))
            return redirect(self.get_payment_url())

        term_last = self.order.payment_term_last
        if term_last and now() > term_last:
            messages.error(request, _('The payment is too late to be accepted.'))
            return redirect(self.get_order_url())

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        try:
            resp = self.payment.payment_provider.execute_payment(request, self.payment)
        except PaymentException as e:
            messages.error(request, str(e))
            return redirect(self.get_order_url())

        if self.order.status == Order.STATUS_PAID:
            return redirect(resp or self.get_order_url() + '?paid=yes')
        else:
            return redirect(resp or self.get_order_url() + '?thanks=yes')

    def get_payment_url(self):
        return eventreverse(
            self.request.event,
            'presale:event.order.pay',
            kwargs={
                'order': self.order.code,
                'payment': self.payment.pk,
                'secret': self.order.secret,
            },
        )


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderPayChangeMethod(EventViewMixin, OrderDetailMixin, TemplateView):
    template_name = 'pretixpresale/event/order_pay_change.html'

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        if self.order.status not in (Order.STATUS_PENDING, Order.STATUS_EXPIRED) or not self.order._can_be_paid():
            messages.error(request, _('The payment method for this order cannot be changed.'))
            return redirect(self.get_order_url())

        term_last = self.order.payment_term_last
        if term_last and now() > term_last:
            messages.error(request, _('The payment is too late to be accepted.'))
            return redirect(self.get_order_url())

        if self.open_payment:
            pp = self.open_payment.payment_provider
            if self.open_payment.state == OrderPayment.PAYMENT_STATE_PENDING and not pp.abort_pending_allowed:
                messages.error(request, _('A payment is currently pending for this order.'))
                return redirect(self.get_order_url())

        return super().dispatch(request, *args, **kwargs)

    def get_payment_url(self, payment):
        return eventreverse(
            self.request.event,
            'presale:event.order.pay',
            kwargs={
                'order': self.order.code,
                'secret': self.order.secret,
                'payment': payment.pk,
            },
        )

    @cached_property
    def open_fees(self):
        e = OrderPayment.objects.filter(
            fee=OuterRef('pk'),
            state__in=(
                OrderPayment.PAYMENT_STATE_CONFIRMED,
                OrderPayment.PAYMENT_STATE_REFUNDED,
            ),
        )
        return self.order.fees.annotate(has_p=Exists(e)).filter(Q(fee_type=OrderFee.FEE_TYPE_PAYMENT) & ~Q(has_p=True))

    @cached_property
    def open_payment(self):
        lp = self.order.payments.last()
        if lp and lp.state not in (
            OrderPayment.PAYMENT_STATE_CONFIRMED,
            OrderPayment.PAYMENT_STATE_REFUNDED,
        ):
            return lp
        return None

    @cached_property
    def _position_sum(self):
        return self.order.positions.aggregate(sum=Sum('price'))['sum'] or Decimal('0.00')

    @transaction.atomic()
    def mark_paid_free(self):
        p = self.order.payments.create(
            state=OrderPayment.PAYMENT_STATE_CREATED,
            provider='manual',
            amount=Decimal('0.00'),
            fee=None,
        )
        try:
            p.confirm()
        except SendMailException:
            pass

    def get(self, request, *args, **kwargs):
        if self.order.pending_sum <= Decimal('0.00'):
            try:
                self.mark_paid_free()
            except Quota.QuotaExceededException as e:
                messages.error(self.request, str(e))
                return redirect(self.get_order_url())
            except PaymentException as e:
                messages.error(self.request, str(e))
                return redirect(self.get_order_url())
            else:
                return redirect(self.get_order_url() + '?paid=1')
        return super().get(request, *args, **kwargs)

    @cached_property
    def provider_forms(self):
        providers = []
        pending_sum = self.order.pending_sum
        for provider in self.request.event.get_payment_providers().values():
            if not provider.is_enabled or not provider.order_change_allowed(self.order):
                continue
            current_fee = sum(f.value for f in self.open_fees) or Decimal('0.00')
            fee = provider.calculate_fee(pending_sum - current_fee)
            if 'order' in inspect.signature(provider.payment_form_render).parameters:
                form = provider.payment_form_render(
                    self.request, abs(pending_sum + fee - current_fee), order=self.order
                )
            elif 'total' in inspect.signature(provider.payment_form_render).parameters:
                form = provider.payment_form_render(self.request, abs(pending_sum + fee - current_fee))
            else:
                form = provider.payment_form_render(self.request)
            providers.append(
                {
                    'provider': provider,
                    'fee': fee,
                    'fee_diff': fee - current_fee,
                    'fee_diff_abs': abs(fee - current_fee),
                    'total': abs(pending_sum + fee - current_fee),
                    'form': form,
                }
            )
        return providers

    def post(self, request, *args, **kwargs):
        self.request = request
        for p in self.provider_forms:
            if p['provider'].identifier == request.POST.get('payment', ''):
                request.session['payment'] = p['provider'].identifier
                request.session['payment_change_{}'.format(self.order.pk)] = '1'

                with transaction.atomic():
                    old_fee, new_fee, fee, newpayment = change_payment_provider(self.order, p['provider'], None)

                resp = p['provider'].payment_prepare(request, newpayment)
                if isinstance(resp, str):
                    return redirect(resp)
                elif resp is True:
                    return redirect(self.get_confirm_url(newpayment))
                else:
                    return self.get(request, *args, **kwargs)
        messages.error(self.request, _('Please select a payment method.'))
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = self.order
        ctx['providers'] = self.provider_forms
        ctx['show_fees'] = any(p['fee_diff'] for p in self.provider_forms)
        return ctx

    def get_confirm_url(self, payment):
        return eventreverse(
            self.request.event,
            'presale:event.order.pay.confirm',
            kwargs={
                'order': self.order.code,
                'secret': self.order.secret,
                'payment': payment.pk,
            },
        )


def can_generate_invoice(event, order, ignore_payments=False):
    v = (
        order.sales_channel in event.settings.get('invoice_generate_sales_channels')
        and (
            event.settings.get('invoice_generate') in ('user', 'True')
            or (event.settings.get('invoice_generate') == 'paid' and order.status == Order.STATUS_PAID)
        )
        and (invoice_qualified(order))
    )
    if not ignore_payments:
        v = v and not (
            not order.payments.exclude(
                state__in=[
                    OrderPayment.PAYMENT_STATE_CANCELED,
                    OrderPayment.PAYMENT_STATE_FAILED,
                ]
            ).exists()
            and order.status == Order.STATUS_PENDING
        )
    return v


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderInvoiceCreate(EventViewMixin, OrderDetailMixin, View):
    def dispatch(self, request, *args, **kwargs):
        self.request = request
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not can_generate_invoice(self.request.event, self.order):
            messages.error(self.request, _('You cannot generate an invoice for this order.'))
        elif self.order.invoices.exists():
            messages.error(self.request, _('An invoice for this order already exists.'))
        else:
            i = generate_invoice(self.order)
            self.order.log_action('pretix.event.order.invoice.generated', data={'invoice': i.pk})
            messages.success(self.request, _('The invoice has been generated.'))
        return redirect(self.get_order_url())


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderModify(EventViewMixin, OrderDetailMixin, OrderQuestionsViewMixin, TemplateView):
    form_class = QuestionsForm
    invoice_form_class = InvoiceAddressForm
    template_name = 'pretixpresale/event/order_modify.html'

    @cached_property
    def positions(self):
        if self.request.GET.get('generate_invoice') == 'true':
            return []
        return super().positions

    def get_question_override_sets(self, order_position):
        override_sets = [
            resp
            for recv, resp in question_form_fields_overrides.send(
                self.request.event, position=order_position, request=self.request
            )
        ]
        for override in override_sets:
            for k in override:
                # We don't want initial values to be modified, they should come from the order directly
                override[k].pop('initial', None)
        return override_sets

    def post(self, request, *args, **kwargs):
        failed = not self.save() or not self.invoice_form.is_valid()
        if failed:
            messages.error(
                self.request,
                _('We had difficulties processing your input. Please review the errors below.'),
            )
            return self.get(request, *args, **kwargs)
        if 'country' in self.invoice_form.cleaned_data:
            trs = TaxRule.objects.filter(id__in=[p.tax_rule_id for p in self.positions])
            for tr in trs:
                if tr.get_matching_rule(self.invoice_form.instance).get('action', 'vat') == 'block':
                    messages.error(
                        self.request,
                        _('One of the selected products is not available in the selected country.'),
                    )
                    return self.get(request, *args, **kwargs)
        if hasattr(self.invoice_form, 'save'):
            self.invoice_form.save()
        self.order.log_action(
            'pretix.event.order.modified',
            {
                'invoice_data': self.invoice_form.cleaned_data,
                'data': [
                    {
                        k: (
                            f.cleaned_data.get(k).name
                            if isinstance(f.cleaned_data.get(k), File)
                            else f.cleaned_data.get(k)
                        )
                        for k in f.changed_data
                    }
                    for f in self.forms
                ],
            },
        )
        order_modified.send(sender=self.request.event, order=self.order)
        if request.GET.get('generate_invoice') == 'true':
            if not can_generate_invoice(self.request.event, self.order):
                messages.error(self.request, _('You cannot generate an invoice for this order.'))
            elif self.order.invoices.exists():
                messages.error(self.request, _('An invoice for this order already exists.'))
            else:
                i = generate_invoice(self.order)
                self.order.log_action('pretix.event.order.invoice.generated', data={'invoice': i.pk})
                messages.success(self.request, _('The invoice has been generated.'))
        elif self.request.event.settings.invoice_reissue_after_modify:
            if self.invoice_form.changed_data:
                inv = self.order.invoices.last()
                if inv and not inv.canceled and not inv.shredded:
                    c = generate_cancellation(inv)
                    if self.order.status != Order.STATUS_CANCELED:
                        inv = generate_invoice(self.order)
                    else:
                        inv = c
                    self.order.log_action('pretix.event.order.invoice.reissued', data={'invoice': inv.pk})
                    messages.success(self.request, _('The invoice has been reissued.'))

        invalidate_cache.apply_async(kwargs={'event': self.request.event.pk, 'order': self.order.pk})
        CachedTicket.objects.filter(order_position__order=self.order).delete()
        CachedCombinedTicket.objects.filter(order=self.order).delete()
        return redirect(self.get_order_url())

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        self.kwargs = kwargs
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        if not self.order.can_modify_answers:
            messages.error(request, _('You cannot modify this order'))
            return redirect(self.get_order_url())
        return super().dispatch(request, *args, **kwargs)


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderCancel(EventViewMixin, OrderDetailMixin, TemplateView):
    template_name = 'pretixpresale/event/order_cancel.html'

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        self.kwargs = kwargs
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        if not self.order.user_cancel_allowed:
            messages.error(request, _('You cannot cancel this order.'))
            return redirect(self.get_order_url())
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = self.order
        prs = self.order.payment_refund_sum
        fee = self.order.user_cancel_fee
        refund_amount = prs - fee
        proposals = self.order.propose_auto_refunds(refund_amount)
        ctx['cancel_fee'] = fee
        ctx['refund_amount'] = refund_amount
        ctx['payment_refund_sum'] = prs
        ctx['can_auto_refund'] = sum(proposals.values()) == refund_amount
        ctx['proposals'] = [p.payment_provider.payment_presale_render(payment=p) for p in proposals]
        if self.request.event.settings.cancel_allow_user_paid_adjust_fees_step:
            steps = [fee]
            s = fee
            while s < prs:
                steps.append(s)
                s += self.request.event.settings.cancel_allow_user_paid_adjust_fees_step
            if prs not in steps:
                steps.append(prs)
            ctx['ticks'] = json.dumps([float(p) for p in steps])
        return ctx


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderCancelDo(EventViewMixin, OrderDetailMixin, AsyncAction, View):
    task = cancel_order
    known_errortypes = ['OrderError']

    def get_success_url(self, value):
        return self.get_order_url()

    def get_error_url(self):
        return self.get_order_url()

    def post(self, request, *args, **kwargs):
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        if not self.order.user_cancel_allowed:
            messages.error(request, _('You cannot cancel this order.'))
            return redirect(self.get_order_url())
        fee = None
        if self.order.status == Order.STATUS_PAID and self.order.total != Decimal('0.00'):
            fee = self.order.user_cancel_fee
        if 'cancel_fee' in request.POST and self.request.event.settings.cancel_allow_user_paid_adjust_fees:
            fee = fee or Decimal('0.00')
            fee_in = re.sub('[^0-9.,]', '', request.POST.get('cancel_fee'))
            try:
                custom_fee = forms.DecimalField(localize=True).to_python(fee_in)
            except:
                try:
                    custom_fee = Decimal(fee_in)
                except:
                    messages.error(request, _('You chose an invalid cancellation fee.'))
                    return redirect(self.get_order_url())
            if custom_fee is not None and fee <= custom_fee <= self.order.payment_refund_sum:
                if self.request.event.settings.cancel_allow_user_paid_adjust_fees_step:
                    if (
                        custom_fee - fee
                    ) % self.request.event.settings.cancel_allow_user_paid_adjust_fees_step != Decimal('0.00'):
                        messages.error(request, _('You chose an invalid cancellation fee.'))
                        return redirect(self.get_order_url())

                fee = custom_fee
            else:
                messages.error(request, _('You chose an invalid cancellation fee.'))
                return redirect(self.get_order_url())
        giftcard = self.request.event.settings.cancel_allow_user_paid_refund_as_giftcard == 'force' or (
            self.request.event.settings.cancel_allow_user_paid_refund_as_giftcard == 'option'
            and self.request.POST.get('giftcard') == 'true'
        )
        if self.request.event.settings.cancel_allow_user_paid_require_approval:
            self.order.cancellation_requests.create(
                cancellation_fee=fee or Decimal('0.00'),
                refund_as_giftcard=giftcard,
            )
            self.order.log_action('pretix.event.order.refund.requested')
            return self.success(None)
        else:
            comment = gettext('Canceled by customer')
            return self.do(
                self.order.pk,
                cancellation_fee=fee,
                try_auto_refund=True,
                refund_as_giftcard=giftcard,
                comment=comment,
            )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = self.order
        return ctx

    def get_success_message(self, value):
        if self.request.event.settings.cancel_allow_user_paid_require_approval:
            return _('The cancellation has been requested.')
        else:
            return _('The order has been canceled.')


@method_decorator(xframe_options_exempt, 'dispatch')
class AnswerDownload(EventViewMixin, OrderDetailMixin, View):
    def get(self, request, *args, **kwargs):
        answid = kwargs.get('answer')
        token = request.GET.get('token', '')

        answer = get_object_or_404(QuestionAnswer, orderposition__order=self.order, id=answid)
        if not answer.file:
            raise Http404()
        if not check_token(request, answer, token):
            raise Http404(_('This link is no longer valid. Please go back, refresh the page, and try again.'))

        ftype, ignored = mimetypes.guess_type(answer.file.name)
        resp = FileResponse(answer.file, content_type=ftype or 'application/binary')
        resp['Content-Disposition'] = 'attachment; filename="{}-{}-{}-{}"'.format(
            self.request.event.slug.upper(),
            self.order.code,
            answer.orderposition.positionid,
            os.path.basename(answer.file.name).split('.', 1)[1],
        )
        return resp


class OrderDownloadMixin:
    def get_success_url(self, value):
        return self.get_self_url()

    @cached_property
    def output(self):
        if not all([r for rr, r in allow_ticket_download.send(self.request.event, order=self.order)]):
            return None
        responses = register_ticket_outputs.send(self.request.event)
        for receiver, response in responses:
            provider = response(self.request.event)
            if provider.identifier == self.kwargs.get('output'):
                return provider

    def get(self, request, *args, **kwargs):
        if not self.output or not self.output.is_enabled:
            return self.error(OrderError(_('You requested an invalid ticket output type.')))
        if 'async_id' in request.GET and settings.HAS_CELERY:
            return self.get_result(request)
        return self.post(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not self.output or not self.output.is_enabled:
            return self.error(OrderError(_('You requested an invalid ticket output type.')))
        if not self.order or ('position' in kwargs and not self.order_position):
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        if not self.order.ticket_download_available:
            return self.error(OrderError(_('Ticket download is not (yet) enabled for this order.')))
        if 'position' in kwargs and not self.order_position.generate_ticket:
            return self.error(OrderError(_('Ticket download is not enabled for this product.')))

        if (
            self.request.event.settings.ticket_download_require_validated_email
            and self.order.sales_channel == 'web'
            and not self.order.email_known_to_work
        ):
            return self.error(OrderError(_('Please click the link we sent you via email to download your tickets.')))

        ct = self.get_last_ct()
        if ct:
            return self.success(ct)
        return self.do(
            'orderposition' if 'position' in kwargs else 'order',
            self.order_position.pk if 'position' in kwargs else self.order.pk,
            self.output.identifier,
        )

    def get_success_message(self, value):
        return ''

    def success(self, value):
        if 'ajax' in self.request.POST or 'ajax' in self.request.GET:
            return JsonResponse(
                {
                    'ready': True,
                    'success': True,
                    'redirect': self.get_success_url(value),
                    'message': str(self.get_success_message(value)),
                }
            )
        if isinstance(value, CachedTicket):
            if value.type == 'text/uri-list':
                resp = HttpResponseRedirect(value.file.file.read())
                return resp
            else:
                resp = FileResponse(value.file.file, content_type=value.type)
                if self.order_position.subevent:
                    # Subevent date in filename improves accessibility e.g. for screen reader users
                    resp['Content-Disposition'] = 'attachment; filename="{}-{}-{}-{}-{}{}"'.format(
                        self.request.event.slug.upper(),
                        self.order.code,
                        self.order_position.positionid,
                        self.order_position.subevent.date_from.strftime('%Y_%m_%d'),
                        self.output.identifier,
                        value.extension,
                    )
                else:
                    resp['Content-Disposition'] = 'attachment; filename="{}-{}-{}-{}{}"'.format(
                        self.request.event.slug.upper(),
                        self.order.code,
                        self.order_position.positionid,
                        self.output.identifier,
                        value.extension,
                    )
                return resp
        elif isinstance(value, CachedCombinedTicket):
            resp = FileResponse(value.file.file, content_type=value.type)
            resp['Content-Disposition'] = 'attachment; filename="{}-{}-{}{}"'.format(
                self.request.event.slug.upper(),
                self.order.code,
                self.output.identifier,
                value.extension,
            )
            return resp
        else:
            return redirect(self.get_self_url())

    def get_last_ct(self):
        if 'position' in self.kwargs:
            ct = CachedTicket.objects.filter(
                order_position=self.order_position,
                provider=self.output.identifier,
                file__isnull=False,
            ).last()
        else:
            ct = CachedCombinedTicket.objects.filter(
                order=self.order, provider=self.output.identifier, file__isnull=False
            ).last()
        if not ct or not ct.file:
            return None
        return ct


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderDownload(OrderDownloadMixin, EventViewMixin, OrderDetailMixin, AsyncAction, View):
    task = generate
    known_errortypes = ['OrderError']

    def get_error_url(self):
        return self.get_order_url()

    def get_self_url(self):
        return eventreverse(
            self.request.event,
            'presale:event.order.download' if 'position' in self.kwargs else 'presale:event.order.download.combined',
            kwargs=self.kwargs,
        )

    @cached_property
    def order_position(self):
        try:
            return self.order.positions.get(pk=self.kwargs.get('position'))
        except OrderPosition.DoesNotExist:
            return None


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderPositionDownload(OrderDownloadMixin, EventViewMixin, OrderPositionDetailMixin, AsyncAction, View):
    task = generate
    known_errortypes = ['OrderError']

    def get_error_url(self):
        return self.get_position_url()

    def get_self_url(self):
        return eventreverse(
            self.request.event,
            'presale:event.order.position.download',
            kwargs=self.kwargs,
        )

    @cached_property
    def order_position(self):
        try:
            return self.order.positions.get(
                Q(pk=self.kwargs.get('pid')) & Q(Q(pk=self.position.pk) | Q(addon_to__id=self.position.pk))
            )
        except OrderPosition.DoesNotExist:
            return None


@method_decorator(xframe_options_exempt, 'dispatch')
class InvoiceDownload(EventViewMixin, OrderDetailMixin, View):
    def get(self, request, *args, **kwargs):
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))

        try:
            invoice = Invoice.objects.get(event=self.request.event, order=self.order, id=self.kwargs['invoice'])
        except Invoice.DoesNotExist:
            raise Http404(_('This invoice has not been found'))

        if not invoice.file:
            invoice_pdf(invoice.pk)
            invoice = Invoice.objects.get(pk=invoice.pk)

        if invoice.shredded:
            messages.error(request, _('The invoice file is no longer stored on the server.'))
            return redirect(self.get_order_url())

        if not invoice.file:
            # This happens if we have celery installed and the file will be generated in the background
            messages.warning(
                request,
                _(
                    'The invoice file has not yet been generated, we will generate it for you '
                    'now. Please try again in a few seconds.'
                ),
            )
            return redirect(self.get_order_url())

        try:
            resp = FileResponse(invoice.file.file, content_type='application/pdf')
        except FileNotFoundError:
            invoice_pdf_task.apply(args=(invoice.pk,))
            return self.get(request, *args, **kwargs)
        resp['Content-Disposition'] = 'inline; filename="{}.pdf"'.format(invoice.number)
        resp._csp_ignore = True  # Some browser's PDF readers do not work with CSP
        return resp


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderChange(EventViewMixin, OrderDetailMixin, TemplateView):
    template_name = 'pretixpresale/event/order_change.html'

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        self.kwargs = kwargs
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))
        if not self.order.user_change_allowed:
            messages.error(request, _('You cannot change this order.'))
            return redirect(self.get_order_url())
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def formdict(self):
        storage = OrderedDict()
        for pos in self.positions:
            if pos.addon_to_id:
                if pos.addon_to not in storage:
                    storage[pos.addon_to] = []
                storage[pos.addon_to].append(pos)
            else:
                if pos not in storage:
                    storage[pos] = []
                storage[pos].append(pos)
        return storage

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = self.order
        ctx['positions'] = self.positions
        ctx['formgroups'] = self.formdict
        return ctx

    @cached_property
    def positions(self):
        positions = list(
            self.order.positions.select_related('item', 'item__tax_rule').prefetch_related(
                'item__quotas', 'item__variations', 'item__variations__quotas'
            )
        )
        try:
            ia = self.order.invoice_address
        except InvoiceAddress.DoesNotExist:
            ia = None
        for p in positions:
            p.form = OrderPositionChangeForm(
                prefix='op-{}'.format(p.pk),
                instance=p,
                invoice_address=ia,
                event=self.request.event,
                data=self.request.POST if self.request.method == 'POST' else None,
            )
        return positions

    def _process_change(self, ocm):
        try:
            ia = self.order.invoice_address
        except InvoiceAddress.DoesNotExist:
            ia = None
        for p in self.positions:
            if not p.form.is_valid():
                return False

            try:
                change_item = None
                if p.form.cleaned_data['itemvar']:
                    if '-' in p.form.cleaned_data['itemvar']:
                        itemid, varid = p.form.cleaned_data['itemvar'].split('-')
                    else:
                        itemid, varid = p.form.cleaned_data['itemvar'], None

                    item = self.request.event.items.get(pk=itemid)
                    if varid:
                        variation = item.variations.get(pk=varid)
                    else:
                        variation = None
                    if item != p.item or variation != p.variation:
                        change_item = (item, variation)

                if change_item is not None:
                    ocm.change_item(p, *change_item)
                    new_price = get_price(
                        change_item[0],
                        change_item[1],
                        voucher=p.voucher,
                        subevent=p.subevent,
                        invoice_address=ia,
                    )

                    if new_price.gross != p.price or new_price.rate != p.tax_rate:
                        ocm.change_price(p, new_price.gross)

                    if change_item[0].tax_rule != p.tax_rule or new_price.rate != p.tax_rate:
                        ocm.change_tax_rule(p, change_item[0].tax_rule)

            except OrderError as e:
                p.custom_error = str(e)
                return False
        return True

    def post(self, *args, **kwargs):
        was_paid = self.order.status == Order.STATUS_PAID
        ocm = OrderChangeManager(
            self.order,
            user=self.request.user,
            notify=True,
            reissue_invoice=True,
        )
        form_valid = self._process_change(ocm)

        if not form_valid:
            messages.error(self.request, _('An error occurred. Please see the details below.'))
        else:
            try:
                ocm.commit(check_quotas=True)
            except OrderError as e:
                messages.error(self.request, str(e))
            else:
                if self.order.status != Order.STATUS_PAID and was_paid:
                    messages.success(
                        self.request,
                        _(
                            'The order has been changed. You can now proceed by paying the open amount of {amount}.'
                        ).format(amount=money_filter(self.order.pending_sum, self.request.event.currency)),
                    )
                    return redirect(
                        eventreverse(
                            self.request.event,
                            'presale:event.order.pay.change',
                            kwargs={
                                'order': self.order.code,
                                'secret': self.order.secret,
                            },
                        )
                    )
                else:
                    messages.success(self.request, _('The order has been changed.'))

                return redirect(self.get_order_url())

        return self.get(*args, **kwargs)
