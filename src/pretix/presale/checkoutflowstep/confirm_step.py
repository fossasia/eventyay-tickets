from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import translation
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from pretix.base.models.orders import Order, OrderPayment
from pretix.base.services.orders import perform_order
from pretix.base.templatetags.rich_text import rich_text_snippet
from pretix.base.views.tasks import AsyncAction
from pretix.multidomain.urlreverse import eventreverse
from pretix.presale.signals import (
    checkout_all_optional,
    checkout_confirm_messages,
    contact_form_fields,
    order_meta_from_request,
)
from pretix.presale.views import CartMixin, get_cart_is_free
from pretix.presale.views.cart import create_empty_cart_id

from .template_flow_step import TemplateFlowStep


class ConfirmStep(CartMixin, AsyncAction, TemplateFlowStep):
    priority = 1001
    identifier = "confirm"
    template_name = "pretixpresale/event/checkout_confirm.html"
    task = perform_order
    known_errortypes = ["OrderError"]
    label = pgettext_lazy("checkoutflow", "Review order")
    icon = "eye"

    def is_applicable(self, request):
        return True

    def is_completed(self, request, warn=False):
        pass

    @cached_property
    def address_asked(self):
        return self.request.event.settings.invoice_address_asked and (
            not self.request.event.settings.invoice_address_not_asked_free
            or not get_cart_is_free(self.request)
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cart"] = self.get_cart(answers=True)
        if self.payment_provider:
            ctx["payment"] = self.payment_provider.checkout_confirm_render(self.request)
            ctx["payment_provider"] = self.payment_provider
        ctx["require_approval"] = any(
            cp.item.require_approval for cp in ctx["cart"]["positions"]
        )
        ctx["addr"] = self.invoice_address
        ctx["confirm_messages"] = self.confirm_messages
        ctx["cart_session"] = self.cart_session
        ctx["invoice_address_asked"] = self.address_asked

        self.cart_session["shown_total"] = str(ctx["cart"]["total"])

        email = self.cart_session.get("contact_form_data", {}).get("email")
        if email != settings.PRETIX_EMAIL_NONE_VALUE:
            ctx["contact_info"] = [
                (_("E-mail"), email),
            ]
        else:
            ctx["contact_info"] = []
        phone = self.cart_session.get("contact_form_data", {}).get("phone")
        if phone:
            ctx["contact_info"].append((_("Phone number"), phone))
        responses = contact_form_fields.send(self.event, request=self.request)
        for r, response in sorted(responses, key=lambda r: str(r[0])):
            for key, value in response.items():
                v = self.cart_session.get("contact_form_data", {}).get(key)
                v = value.bound_data(v, initial="")
                if v is True:
                    v = _("Yes")
                elif v is False:
                    v = _("No")
                ctx["contact_info"].append((rich_text_snippet(value.label), v))

        return ctx

    @cached_property
    def confirm_messages(self):
        if self.all_optional:
            return {}
        msgs = {}
        responses = checkout_confirm_messages.send(self.request.event)
        for receiver, response in responses:
            msgs.update(response)
        return msgs

    @cached_property
    def payment_provider(self):
        if "payment" not in self.cart_session:
            return None
        return self.request.event.get_payment_providers().get(
            self.cart_session["payment"]
        )

    def get(self, request):
        self.request = request
        if "async_id" in request.GET and settings.HAS_CELERY:
            return self.get_result(request)
        return TemplateFlowStep.get(self, request)

    @cached_property
    def all_optional(self):
        for recv, resp in checkout_all_optional.send(
            sender=self.request.event, request=self.request
        ):
            if resp:
                return True
        return False

    def post(self, request):
        self.request = request

        if self.confirm_messages and not self.all_optional:
            for key, msg in self.confirm_messages.items():
                if request.POST.get("confirm_{}".format(key)) != "yes":
                    msg = str(
                        _("You need to check all checkboxes on the bottom of the page.")
                    )
                    messages.error(self.request, msg)
                    if "ajax" in self.request.POST or "ajax" in self.request.GET:
                        return JsonResponse(
                            {
                                "ready": True,
                                "redirect": self.get_error_url(),
                                "message": msg,
                            }
                        )
                    return redirect(self.get_error_url())

        meta_info = {
            "contact_form_data": self.cart_session.get("contact_form_data", {}),
            "confirm_messages": [str(m) for m in self.confirm_messages.values()],
        }
        for receiver, response in order_meta_from_request.send(
            sender=request.event, request=request
        ):
            meta_info.update(response)

        return self.do(
            self.request.event.id,
            self.payment_provider.identifier if self.payment_provider else None,
            [p.id for p in self.positions],
            self.cart_session.get("email"),
            translation.get_language(),
            self.invoice_address.pk,
            meta_info,
            request.sales_channel.identifier,
            self.cart_session.get("gift_cards"),
            self.cart_session.get("shown_total"),
        )

    def get_success_message(self, value):
        create_empty_cart_id(self.request)
        return None

    def get_success_url(self, value):
        order = Order.objects.get(id=value)
        return self.get_order_url(order)

    def get_error_message(self, exception):
        if exception.__class__.__name__ == "SendMailException":
            return _(
                "There was an error sending the confirmation mail. Please try again later."
            )
        return super().get_error_message(exception)

    def get_error_url(self):
        return self.get_step_url(self.request)

    def get_order_url(self, order):
        payment = order.payments.filter(
            state=OrderPayment.PAYMENT_STATE_CREATED
        ).first()
        if not payment:
            return (
                eventreverse(
                    self.request.event,
                    "presale:event.order",
                    kwargs={
                        "order": order.code,
                        "secret": order.secret,
                    },
                )
                + "?thanks=1"
            )
        return eventreverse(
            self.request.event,
            "presale:event.order.pay.complete",
            kwargs={"order": order.code, "secret": order.secret, "payment": payment.pk},
        )
