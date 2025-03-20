import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce
from django.forms import DecimalField
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from pretix.base.models.giftcards import (
    GiftCard,
    GiftCardTransaction,
    gen_giftcard_secret,
)
from pretix.base.models.orders import OrderPayment
from pretix.base.models.organizer import Organizer
from pretix.base.payment import PaymentException
from pretix.control.forms.filter import GiftCardFilterForm
from pretix.control.forms.organizer_forms import (
    GiftCardCreateForm,
    GiftCardUpdateForm,
)
from pretix.control.permissions import OrganizerPermissionRequiredMixin
from pretix.control.views.organizer_views.organizer_detail_view_mixin import (
    OrganizerDetailViewMixin,
)


class GiftCardListView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView):
    model = GiftCard
    template_name = 'pretixcontrol/organizers/giftcards.html'
    permission = 'can_manage_gift_cards'
    context_object_name = 'giftcards'
    paginate_by = 50

    def get_queryset(self):
        s = (
            GiftCardTransaction.objects.filter(card=OuterRef('pk'))
            .order_by()
            .values('card')
            .annotate(s=Sum('value'))
            .values('s')
        )
        qs = self.request.organizer.issued_gift_cards.annotate(
            cached_value=Coalesce(Subquery(s), Decimal('0.00'))
        ).order_by('-issuance')
        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)
        return qs

    def post(self, request, *args, **kwargs):
        if 'add' in request.POST:
            o = (
                self.request.user.get_organizers_with_permission('can_manage_gift_cards', self.request)
                .exclude(pk=self.request.organizer.pk)
                .filter(slug=request.POST.get('add'))
                .first()
            )
            if o:
                self.request.organizer.gift_card_issuer_acceptance.get_or_create(issuer=o)
                self.request.organizer.log_action(
                    'pretix.giftcards.acceptance.added',
                    data={'issuer': o.slug},
                    user=request.user,
                )
                messages.success(self.request, _('The selected gift card issuer has been added.'))
        if 'del' in request.POST:
            o = Organizer.objects.filter(slug=request.POST.get('del')).first()
            if o:
                self.request.organizer.gift_card_issuer_acceptance.filter(issuer=o).delete()
                self.request.organizer.log_action(
                    'pretix.giftcards.acceptance.removed',
                    data={'issuer': o.slug},
                    user=request.user,
                )
                messages.success(self.request, _('The selected gift card issuer has been removed.'))
        return redirect(
            reverse(
                'control:organizer.giftcards',
                kwargs={'organizer': self.request.organizer.slug},
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        ctx['other_organizers'] = self.request.user.get_organizers_with_permission(
            'can_manage_gift_cards', self.request
        ).exclude(pk=self.request.organizer.pk)
        return ctx

    @cached_property
    def filter_form(self):
        return GiftCardFilterForm(data=self.request.GET, request=self.request)


class GiftCardDetailView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DetailView):
    template_name = 'pretixcontrol/organizers/giftcard.html'
    permission = 'can_manage_gift_cards'
    context_object_name = 'card'

    def get_object(self, queryset=None) -> Organizer:
        return get_object_or_404(self.request.organizer.issued_gift_cards, pk=self.kwargs.get('giftcard'))

    @transaction.atomic()
    def post(self, request, *args, **kwargs):
        self.object = GiftCard.objects.select_for_update().get(pk=self.get_object().pk)
        if 'revert' in request.POST:
            t = get_object_or_404(
                self.object.transactions.all(),
                pk=request.POST.get('revert'),
                order__isnull=False,
            )
            if self.object.value - t.value < Decimal('0.00'):
                messages.error(request, _('Gift cards are not allowed to have negative values.'))
            elif t.value > 0:
                r = t.order.payments.create(
                    order=t.order,
                    state=OrderPayment.PAYMENT_STATE_CREATED,
                    amount=t.value,
                    provider='giftcard',
                    info=json.dumps(
                        {
                            'gift_card': self.object.pk,
                            'retry': True,
                        }
                    ),
                )
                try:
                    r.payment_provider.execute_payment(request, r)
                except PaymentException as e:
                    with transaction.atomic():
                        r.state = OrderPayment.PAYMENT_STATE_FAILED
                        r.save()
                        t.order.log_action(
                            'pretix.event.order.payment.failed',
                            {
                                'local_id': r.local_id,
                                'provider': r.provider,
                                'error': str(e),
                            },
                        )
                    messages.error(request, _('The transaction could not be reversed.'))
                else:
                    messages.success(request, _('The transaction has been reversed.'))
        elif 'value' in request.POST:
            try:
                value = DecimalField(localize=True).to_python(request.POST.get('value'))
            except ValidationError:
                messages.error(request, _('Your input was invalid, please try again.'))
            else:
                if self.object.value + value < Decimal('0.00'):
                    messages.error(
                        request,
                        _('Gift cards are not allowed to have negative values.'),
                    )
                else:
                    self.object.transactions.create(
                        value=value,
                        text=request.POST.get('text') or None,
                    )
                    self.object.log_action(
                        'pretix.giftcards.transaction.manual',
                        data={'value': value, 'text': request.POST.get('text')},
                        user=self.request.user,
                    )
                    messages.success(request, _('The manual transaction has been saved.'))
                    return redirect(
                        reverse(
                            'control:organizer.giftcard',
                            kwargs={
                                'organizer': request.organizer.slug,
                                'giftcard': self.object.pk,
                            },
                        )
                    )
        return self.get(request, *args, **kwargs)


class GiftCardCreateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, CreateView):
    template_name = 'pretixcontrol/organizers/giftcard_create.html'
    permission = 'can_manage_gift_cards'
    form_class = GiftCardCreateForm
    success_url = 'invalid'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        any_event = self.request.organizer.events.first()
        kwargs['initial'] = {
            'currency': any_event.currency if any_event else settings.DEFAULT_CURRENCY,
            'secret': gen_giftcard_secret(self.request.organizer.settings.giftcard_length),
        }
        kwargs['organizer'] = self.request.organizer
        return kwargs

    @transaction.atomic()
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, _('The gift card has been created and can now be used.'))
        form.instance.issuer = self.request.organizer
        super().form_valid(form)
        form.instance.transactions.create(value=form.cleaned_data['value'])
        form.instance.log_action('pretix.giftcards.created', user=self.request.user, data={})
        if form.cleaned_data['value']:
            form.instance.log_action(
                'pretix.giftcards.transaction.manual',
                user=self.request.user,
                data={'value': form.cleaned_data['value']},
            )
        return redirect(
            reverse(
                'control:organizer.giftcard',
                kwargs={
                    'organizer': self.request.organizer.slug,
                    'giftcard': self.object.pk,
                },
            )
        )


class GiftCardUpdateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, UpdateView):
    template_name = 'pretixcontrol/organizers/giftcard_edit.html'
    permission = 'can_manage_gift_cards'
    form_class = GiftCardUpdateForm
    success_url = 'invalid'
    context_object_name = 'card'
    model = GiftCard

    def get_object(self, queryset=None) -> Organizer:
        return get_object_or_404(self.request.organizer.issued_gift_cards, pk=self.kwargs.get('giftcard'))

    @transaction.atomic()
    def form_valid(self, form):
        messages.success(self.request, _('The gift card has been changed.'))
        super().form_valid(form)
        form.instance.log_action(
            'pretix.giftcards.modified',
            user=self.request.user,
            data=dict(form.cleaned_data),
        )
        return redirect(
            reverse(
                'control:organizer.giftcard',
                kwargs={
                    'organizer': self.request.organizer.slug,
                    'giftcard': self.object.pk,
                },
            )
        )
