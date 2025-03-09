from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from pretix.base.models import TaxRule
from pretix.base.services.cart import update_tax_rates
from pretix.presale.checkoutflowstep.template_flow_step import TemplateFlowStep
from pretix.presale.forms.checkout import (
    ContactForm,
    InvoiceAddressForm,
    InvoiceNameForm,
)
from pretix.presale.signals import (
    checkout_all_optional,
    contact_form_fields_overrides,
    question_form_fields,
    question_form_fields_overrides,
)
from pretix.presale.views import CartMixin, get_cart_is_free
from pretix.presale.views.cart import get_or_create_cart_id
from pretix.presale.views.questions import QuestionsViewMixin


class QuestionsStep(QuestionsViewMixin, CartMixin, TemplateFlowStep):
    priority = 50
    identifier = "questions"
    template_name = "pretixpresale/event/checkout_questions.html"
    label = pgettext_lazy("checkoutflow", "Your information")

    def is_applicable(self, request):
        return True

    @cached_property
    def all_optional(self):
        for recv, resp in checkout_all_optional.send(
            sender=self.request.event, request=self.request
        ):
            if resp:
                return True
        return False

    @cached_property
    def _contact_override_sets(self):
        return [
            resp
            for recv, resp in contact_form_fields_overrides.send(
                self.request.event,
                request=self.request,
                order=None,
            )
        ]

    @cached_property
    def contact_form(self):
        wd = self.cart_session.get("widget_data", {})
        initial = {
            "email": (
                (self.request.user.email if self.request.user.is_authenticated else "")
                or self.cart_session.get("email", "")
                or wd.get("email", "")
            ),
            "phone": wd.get("phone", None),
        }
        initial.update(self.cart_session.get("contact_form_data", {}))

        override_sets = self._contact_override_sets
        for overrides in override_sets:
            initial.update(
                {k: v["initial"] for k, v in overrides.items() if "initial" in v}
            )

        f = ContactForm(
            data=self.request.POST if self.request.method == "POST" else None,
            event=self.request.event,
            request=self.request,
            initial=initial,
            all_optional=self.all_optional,
        )
        if wd.get("email", "") and wd.get("fix", "") == "true":
            f.fields["email"].disabled = True

        for overrides in override_sets:
            for fname, val in overrides.items():
                if "disabled" in val and fname in f.fields:
                    f.fields[fname].disabled = val["disabled"]

        return f

    def get_question_override_sets(self, cart_position):
        return [
            resp
            for recv, resp in question_form_fields_overrides.send(
                self.request.event, position=cart_position, request=self.request
            )
        ]

    @cached_property
    def eu_reverse_charge_relevant(self):
        return any(
            [
                p.item.tax_rule
                and (p.item.tax_rule.eu_reverse_charge or p.item.tax_rule.custom_rules)
                for p in self.positions
            ]
        )

    @cached_property
    def invoice_form(self):
        wd = self.cart_session.get("widget_data", {})
        if not self.invoice_address.pk:
            wd_initial = {
                "name_parts": {
                    k[21:].replace("-", "_"): v
                    for k, v in wd.items()
                    if k.startswith("invoice-address-name-")
                },
                "company": wd.get("invoice-address-company", ""),
                "is_business": bool(wd.get("invoice-address-company", "")),
                "street": wd.get("invoice-address-street", ""),
                "zipcode": wd.get("invoice-address-zipcode", ""),
                "city": wd.get("invoice-address-city", ""),
                "country": wd.get("invoice-address-country", ""),
            }
        else:
            wd_initial = {}
        initial = dict(wd_initial)

        override_sets = self._contact_override_sets
        for overrides in override_sets:
            initial.update(
                {k: v["initial"] for k, v in overrides.items() if "initial" in v}
            )

        if not self.address_asked and self.request.event.settings.invoice_name_required:
            f = InvoiceNameForm(
                data=self.request.POST if self.request.method == "POST" else None,
                event=self.request.event,
                request=self.request,
                instance=self.invoice_address,
                initial=initial,
                validate_vat_id=False,
                all_optional=self.all_optional,
            )
        else:
            f = InvoiceAddressForm(
                data=self.request.POST if self.request.method == "POST" else None,
                event=self.request.event,
                request=self.request,
                initial=initial,
                instance=self.invoice_address,
                validate_vat_id=self.eu_reverse_charge_relevant,
                all_optional=self.all_optional,
            )
        for name, field in f.fields.items():
            if wd_initial.get(name) and wd.get("fix", "") == "true":
                field.disabled = True

        for overrides in override_sets:
            for fname, val in overrides.items():
                if "disabled" in val and fname in f.fields:
                    f.fields[fname].disabled = val["disabled"]

        return f

    @cached_property
    def address_asked(self):
        return self.request.event.settings.invoice_address_asked and (
            not self.request.event.settings.invoice_address_not_asked_free
            or not get_cart_is_free(self.request)
        )

    def post(self, request):
        self.request = request
        failed = not self.save() or not self.contact_form.is_valid()
        if self.address_asked or self.request.event.settings.invoice_name_required:
            failed = failed or not self.invoice_form.is_valid()
        if failed:
            messages.error(
                request,
                _(
                    "We had difficulties processing your input. Please review the errors below."
                ),
            )
            return self.render()
        self.cart_session["email"] = self.contact_form.cleaned_data["email"]
        d = dict(self.contact_form.cleaned_data)
        if d.get("phone"):
            d["phone"] = str(d["phone"])
        self.cart_session["contact_form_data"] = d
        if self.address_asked or self.request.event.settings.invoice_name_required:
            addr = self.invoice_form.save()
            try:
                diff = update_tax_rates(
                    event=request.event,
                    cart_id=get_or_create_cart_id(request),
                    invoice_address=addr,
                )
            except TaxRule.SaleNotAllowed:
                messages.error(
                    request,
                    _(
                        "Unfortunately, based on the invoice address you entered, we're not able to sell you "
                        "the selected products for tax-related legal reasons."
                    ),
                )
                return self.render()

            self.cart_session["invoice_address"] = addr.pk
            if abs(diff) > Decimal("0.001"):
                messages.info(
                    request,
                    _(
                        "Due to the invoice address you entered, we need to apply a different tax "
                        "rate to your purchase and the price of the products in your cart has "
                        "changed accordingly."
                    ),
                )
                return redirect(self.get_next_url(request) + "?open_cart=true")

        return redirect(self.get_next_url(request))

    def is_completed(self, request, warn=False):
        self.request = request
        try:
            emailval = EmailValidator()
            if not self.cart_session.get("email") and not self.all_optional:
                if warn:
                    messages.warning(request, _("Please enter a valid email address."))
                return False
            if self.cart_session.get("email"):
                emailval(self.cart_session.get("email"))
        except ValidationError:
            if warn:
                messages.warning(request, _("Please enter a valid email address."))
            return False

        if not self.all_optional:

            if self.address_asked:
                if request.event.settings.invoice_address_required and (
                    not self.invoice_address or not self.invoice_address.street
                ):
                    messages.warning(request, _("Please enter your invoicing address."))
                    return False

            if request.event.settings.invoice_name_required and (
                not self.invoice_address or not self.invoice_address.name
            ):
                messages.warning(request, _("Please enter your name."))
                return False

        for cp in self._positions_for_questions:
            answ = {aw.question_id: aw for aw in cp.answerlist}
            question_cache = {q.pk: q for q in cp.item.questions_to_ask}

            def question_is_visible(parentid, qvals):
                if parentid not in question_cache:
                    return False
                parentq = question_cache[parentid]
                if parentq.dependency_question_id and not question_is_visible(
                    parentq.dependency_question_id, parentq.dependency_values
                ):
                    return False
                if parentid not in answ:
                    return False
                return (
                    ("True" in qvals and answ[parentid].answer == "True")
                    or ("False" in qvals and answ[parentid].answer == "False")
                    or (
                        any(
                            qval in [o.identifier for o in answ[parentid].options.all()]
                            for qval in qvals
                        )
                    )
                )

            def question_is_required(q):
                return q.required and (
                    not q.dependency_question_id
                    or question_is_visible(
                        q.dependency_question_id, q.dependency_values
                    )
                )

            for q in cp.item.questions_to_ask:
                if question_is_required(q) and q.id not in answ:
                    if warn:
                        messages.warning(
                            request,
                            _("Please fill in answers to all required questions."),
                        )
                    return False
            if (
                cp.item.admission
                and self.request.event.settings.get(
                    "attendee_names_required", as_type=bool
                )
                and not cp.attendee_name_parts
            ):
                if warn:
                    messages.warning(
                        request, _("Please fill in answers to all required questions.")
                    )
                return False
            if (
                cp.item.admission
                and self.request.event.settings.get(
                    "attendee_emails_required", as_type=bool
                )
                and cp.attendee_email is None
            ):
                if warn:
                    messages.warning(
                        request, _("Please fill in answers to all required questions.")
                    )
                return False
            if (
                cp.item.admission
                and self.request.event.settings.get(
                    "attendee_company_required", as_type=bool
                )
                and cp.company is None
            ):
                if warn:
                    messages.warning(
                        request, _("Please fill in answers to all required questions.")
                    )
                return False
            if (
                cp.item.admission
                and self.request.event.settings.get(
                    "attendee_attendees_required", as_type=bool
                )
                and (cp.street is None or cp.city is None or cp.country is None)
            ):
                if warn:
                    messages.warning(
                        request, _("Please fill in answers to all required questions.")
                    )
                return False

            responses = question_form_fields.send(
                sender=self.request.event, position=cp
            )
            form_data = cp.meta_info_data.get("question_form_data", {})
            for r, response in sorted(responses, key=lambda r: str(r[0])):
                for key, value in response.items():
                    if value.required and not form_data.get(key):
                        return False
        return True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["formgroups"] = self.formdict.items()
        ctx["contact_form"] = self.contact_form
        ctx["invoice_form"] = self.invoice_form
        ctx["reverse_charge_relevant"] = self.eu_reverse_charge_relevant
        ctx["cart"] = self.get_cart()
        ctx["cart_session"] = self.cart_session
        ctx["invoice_address_asked"] = self.address_asked
        return ctx
