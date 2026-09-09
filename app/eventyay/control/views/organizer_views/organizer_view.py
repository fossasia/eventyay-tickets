import logging
import os

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Max, Min, Prefetch
from django.db.models.functions import Coalesce, Greatest
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import (
    CreateView,
    FormView,
    ListView,
    UpdateView,
)
from rest_framework.decorators import api_view
from rest_framework.response import Response

from eventyay.base.models.event import Event, EventMetaValue
from eventyay.base.models.organizer import Organizer, OrganizerBillingModel, Team
from eventyay.base.settings import (
    DEFAULTS,
    SETTINGS_AFFECTING_CSS,
    is_event_series_creation_enabled,
    is_meetup_creation_enabled,
)
from eventyay.common.text.path import resolve_media_path
from eventyay.control.forms.filter import EventFilterForm, OrganizerFilterForm, advanced_filters_open_from_get
from eventyay.control.forms.organizer_forms import (
    OrganizerDeleteForm,
    OrganizerForm,
    OrganizerSettingsForm,
    OrganizerUpdateForm,
)
from eventyay.control.permissions import (
    AdministratorPermissionRequiredMixin,
    OrganizerCreationPermissionMixin,
    OrganizerPermissionRequiredMixin,
)
from eventyay.control.signals import nav_organizer
from eventyay.control.tasks import delete_organizer_data
from eventyay.control.views import PaginationMixin
from eventyay.eventyay_common.views.organizer_analytics import OrganizerAnalyticsView
from eventyay.helpers.stripe_utils import (
    create_setup_intent,
    get_payment_method_info,
    get_stripe_customer_id,
    get_stripe_publishable_key,
    update_payment_info,
)
from eventyay.presale.style import regenerate_organizer_css

from ...forms.organizer_forms.organizer_form import BillingSettingsForm
from .organizer_detail_view_mixin import OrganizerDetailViewMixin


logger = logging.getLogger(__name__)


class OrganizerCreate(OrganizerCreationPermissionMixin, CreateView):
    model = Organizer
    form_class = OrganizerForm
    template_name = 'pretixcontrol/organizers/create.html'
    context_object_name = 'organizer'

    def dispatch(self, request, *args, **kwargs):
        # Check if user has permission to create organizers
        if not self._can_create_organizer(request.user):
            raise PermissionDenied(
                _('You do not have permission to create organizers. Please contact an administrator.')
            )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['request'] = self.request
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, _('The new organizer has been created.'))
        had_default = bool(self.request.user.get_default_organizer())
        ret = super().form_valid(form)
        t = Team.objects.create(
            organizer=form.instance,
            name=_('Core Organizing Team'),
            all_events=True,
            can_create_events=True,
            can_change_teams=True,
            can_manage_gift_cards=True,
            can_change_organizer_settings=True,
            can_change_event_settings=True,
            can_change_config=True,
            can_change_items=True,
            can_view_orders=True,
            can_change_orders=True,
            can_manage_bank_transfers=True,
            can_checkin_orders=True,
            can_view_vouchers=True,
            can_change_vouchers=True,
            can_change_submissions=True,
            is_reviewer=True,
            can_change_exhibition_proposals=True,
            is_exhibition_reviewer=True,
            can_manage_social_media=True,
            can_video_manage_content=True,
            can_video_moderate=True,
            can_video_manage_kiosks=True,
            can_video_view_analytics=True,
        )
        t.members.add(self.request.user)
        if form.cleaned_data.get('set_as_default') or not had_default:
            self.request.user.default_organizer = self.object
            self.request.user.save(update_fields=['default_organizer'])
        return ret

    def get_success_url(self) -> str:
        return reverse(
            'control:organizer',
            kwargs={
                'organizer': self.object.slug,
            },
        )


class OrganizerUpdate(OrganizerPermissionRequiredMixin, UpdateView):
    model = Organizer
    form_class = OrganizerUpdateForm
    template_name = 'pretixcontrol/organizers/edit.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'organizer'

    @cached_property
    def object(self) -> Organizer:
        return self.request.organizer

    def get_object(self, queryset=None) -> Organizer:
        return self.object

    @cached_property
    def sform(self):
        return OrganizerSettingsForm(
            obj=self.object,
            prefix='settings',
            data=self.request.POST if self.request.method == 'POST' else None,
            files=self.request.FILES if self.request.method == 'POST' else None,
        )

    def get_context_data(self, *args, **kwargs) -> dict:
        context = super().get_context_data(*args, **kwargs)
        context['sform'] = self.sform
        return context

    @transaction.atomic
    def form_valid(self, form):
        self.sform.save()
        change_css = False
        if self.sform.has_changed():
            self.request.organizer.log_action(
                'pretix.organizer.settings',
                user=self.request.user,
                data={
                    k: (
                        self.sform.cleaned_data.get(k).name
                        if isinstance(self.sform.cleaned_data.get(k), File)
                        else self.sform.cleaned_data.get(k)
                    )
                    for k in self.sform.changed_data
                },
            )
            if any(p in self.sform.changed_data for p in SETTINGS_AFFECTING_CSS):
                change_css = True
        if form.has_changed():
            self.request.organizer.log_action(
                'pretix.organizer.changed',
                user=self.request.user,
                data={k: form.cleaned_data.get(k) for k in form.changed_data},
            )

        if 'set_as_default' in form.cleaned_data:
            if form.cleaned_data['set_as_default']:
                if self.request.user.teams.filter(organizer=self.object).exists():
                    self.request.user.default_organizer = self.object
                    self.request.user.save(update_fields=['default_organizer'])
            else:
                if self.request.user.default_organizer_id == self.object.id:
                    self.request.user.default_organizer = None
                    self.request.user.save(update_fields=['default_organizer'])

        if change_css:
            # Force CSS regeneration even if a checksum exists.
            self.request.organizer.settings.delete('presale_css_checksum')
            transaction.on_commit(lambda: regenerate_organizer_css.apply_async(args=(self.request.organizer.pk,)))
            messages.success(
                self.request,
                _(
                    'Your changes have been saved. Please note that it can '
                    'take a short period of time until your changes become '
                    'active.'
                ),
            )
        else:
            messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        if self.request.user.has_active_staff_session(self.request.session.session_key):
            # Custom domain feature is temporarily disabled.
            # Uncomment when the feature is ready for re-enablement.
            # kwargs['domain'] = True
            kwargs['change_slug'] = True
        return kwargs

    def get_success_url(self) -> str:
        return reverse(
            'eventyay_common:organizer.edit',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.POST.get('ajax') == 'delete_image':
            setting_key = request.POST.get('setting_key', '').strip()
            if not setting_key:
                field = request.POST.get('field', '').strip()
                if field.startswith('settings-'):
                    setting_key = field[len('settings-'):]
                else:
                    setting_key = field

            if setting_key in DEFAULTS and DEFAULTS[setting_key].get('type') is File:
                current_value = self.object.settings.get(setting_key, as_type=str)
                if current_value:
                    current_file = resolve_media_path(current_value)
                    if current_file and not str(current_file).startswith(('http://', 'https://')):
                        default_storage.delete(current_file)
                        base_path, unused_ext = os.path.splitext(current_file)
                        orig_ext = self.object.settings.get(f'{setting_key}_original_ext', as_type=str)
                        if orig_ext:
                            default_storage.delete(f'{base_path}_original.{orig_ext}')

                if self.object.settings.get(setting_key) is not None:
                    del self.object.settings[setting_key]
                orig_ext_key = f"{setting_key}_original_ext"
                if self.object.settings.get(orig_ext_key) is not None:
                    del self.object.settings[orig_ext_key]
                self.request.organizer.log_action('pretix.organizer.settings', user=request.user, data={setting_key: None})
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': 'Invalid field'}, status=400)

        form = self.get_form()
        if form.is_valid() and self.sform.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


class OrganizerDelete(AdministratorPermissionRequiredMixin, FormView):
    model = Organizer
    template_name = 'pretixcontrol/organizers/delete.html'
    context_object_name = 'organizer'
    form_class = OrganizerDeleteForm

    def post(self, request, *args, **kwargs):
        if not self.request.organizer.allow_delete():
            messages.error(self.request, _('This organizer can not be deleted.'))
            return self.get(self.request, *self.args, **self.kwargs)
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def form_valid(self, form):
        organizer_id = self.request.organizer.pk
        user_id = self.request.user.pk

        self.request.organizer.log_action(
            'eventyay.organizer.deletion.scheduled',
            user=self.request.user,
            data={
                'name': str(self.request.organizer.name),
            },
        )
        transaction.on_commit(
            lambda: delete_organizer_data.apply_async(kwargs={'organizer_id': organizer_id, 'user_id': user_id})
        )
        messages.success(
            self.request,
            _(
                'The organizer deletion has been scheduled and will continue in the background. '
                'If the organizer is still visible after a short while, check the organizer logs for the outcome.'
            ),
        )
        return redirect(self.get_success_url())

    def get_success_url(self) -> str:
        return reverse('eventyay_common:dashboard')


class OrganizerDisplaySettings(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, View):
    permission = None

    def get(self, request, *wargs, **kwargs):
        return redirect(
            reverse(
                'eventyay_common:organizer.edit',
                kwargs={
                    'organizer': self.request.organizer.slug,
                },
            )
            + '#tab-0-3-open'
        )


class OrganizerSettingsFormView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, FormView):
    model = Organizer
    permission = 'can_change_organizer_settings'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.request.organizer
        return kwargs

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            form.save()
            if form.has_changed():
                self.request.organizer.log_action(
                    'pretix.organizer.settings',
                    user=self.request.user,
                    data={
                        k: (
                            form.cleaned_data.get(k).name
                            if isinstance(form.cleaned_data.get(k), File)
                            else form.cleaned_data.get(k)
                        )
                        for k in form.changed_data
                    },
                )
            messages.success(self.request, _('Your changes have been saved.'))
            return redirect(self.get_success_url())
        else:
            messages.error(
                self.request,
                _('We could not save your changes. See below for details.'),
            )
            return self.get(request)

class OrganizerDashboard(OrganizerDetailViewMixin, OrganizerAnalyticsView):
    template_name = 'eventyay_common/organizers/dashboard.html'
    permission = None

    @property
    def organizer(self):
        return self.request.organizer

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['event_series_creation_enabled'] = is_event_series_creation_enabled(self.request)
        ctx['meetup_creation_enabled'] = is_meetup_creation_enabled(self.request)
        ctx['has_any_analytics'] = any([
            ctx.get('has_orders'),
            ctx.get('has_proposals'),
            ctx.get('show_checkins'),
            ctx.get('has_attendance'),
            ctx.get('has_email_engagement'),
            ctx.get('has_followers'),
        ])
        return ctx


class OrganizerDetail(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView):
    model = Event
    template_name = 'pretixcontrol/organizers/detail.html'
    permission = None
    context_object_name = 'events'
    paginate_by = 50

    @property
    def organizer(self):
        return self.request.organizer

    def get_queryset(self):
        qs = (
            self.request.user.get_events_with_any_permission(self.request)
            .select_related('organizer')
            .prefetch_related(
                'organizer',
                '_settings_objects',
                'organizer___settings_objects',
                'organizer__meta_properties',
                Prefetch(
                    'meta_values',
                    EventMetaValue.objects.select_related('property'),
                    to_attr='meta_values_cached',
                ),
            )
            .filter(organizer=self.request.organizer)
            .order_by('-date_from')
        )
        qs = qs.annotate(
            min_from=Min('subevents__date_from'),
            max_from=Max('subevents__date_from'),
            max_to=Max('subevents__date_to'),
            max_fromto=Greatest(Max('subevents__date_to'), Max('subevents__date_from')),
        ).annotate(
            order_from=Coalesce('min_from', 'date_from'),
            order_to=Coalesce('max_fromto', 'max_to', 'max_from', 'date_to', 'date_from'),
        )
        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)
        return qs

    @cached_property
    def filter_form(self):
        return EventFilterForm(data=self.request.GET, request=self.request, organizer=self.organizer)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        ctx['advanced_filters_open'] = advanced_filters_open_from_get(self.filter_form)
        ctx['meta_fields'] = [self.filter_form[f'meta_{p.name}'] for p in self.organizer.meta_properties.all()]
        ctx['event_series_creation_enabled'] = is_event_series_creation_enabled(self.request)
        ctx['meetup_creation_enabled'] = is_meetup_creation_enabled(self.request)
        return ctx


class OrganizerDetailViewMixin:
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['nav_organizer'] = []
        ctx['organizer'] = self.request.organizer

        for recv, retv in nav_organizer.send(
            sender=self.request.organizer,
            request=self.request,
            organizer=self.request.organizer,
        ):
            ctx['nav_organizer'] += retv
        ctx['nav_organizer'].sort(key=lambda n: n['label'])
        return ctx

    def get_object(self, queryset=None) -> Organizer:
        return self.request.organizer


class OrganizerList(OrganizerCreationPermissionMixin, PaginationMixin, ListView):
    model = Organizer
    context_object_name = 'organizers'
    template_name = 'pretixcontrol/organizers/index.html'

    def get_queryset(self):
        qs = Organizer.objects.all()
        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)
        if self.request.user.has_active_staff_session(self.request.session.session_key):
            return qs
        else:
            return qs.filter(pk__in=self.request.user.teams.values_list('organizer', flat=True))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        ctx['can_create_organizer'] = self._can_create_organizer(self.request.user)
        ctx['default_organizer'] = (
            self.request.user.get_default_organizer() if self.request.user.is_authenticated else None
        )
        return ctx

    @cached_property
    def filter_form(self):
        return OrganizerFilterForm(data=self.request.GET, request=self.request)


class BillingSettings(FormView, OrganizerPermissionRequiredMixin):
    model = OrganizerBillingModel
    form_class = BillingSettingsForm
    template_name = 'pretixcontrol/organizers/billing.html'
    permission = 'can_change_organizer_settings'

    def get_success_url(self):
        return reverse(
            'eventyay_common:organizer.billing',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        billing_settings = OrganizerBillingModel.objects.filter(organizer_id=self.request.organizer.id).first()

        if billing_settings and billing_settings.stripe_customer_id:
            ctx['is_general_information_fulfilled'] = True
        else:
            ctx['is_general_information_fulfilled'] = False
        return ctx

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.has_changed():
            if form.is_valid():
                if form.warning_message:
                    messages.warning(self.request, _(form.warning_message))
                try:
                    form.save()
                    messages.success(self.request, _('Your changes have been saved.'))
                    return redirect(self.get_success_url())
                except ValidationError as e:
                    logger.error('Validation error saving billing settings: %s', str(e))
                    messages.error(self.request, _(str(e.messages[0])))
            else:
                messages.error(
                    self.request,
                    _('We could not save your changes. See below for details.'),
                )
            return self.form_invalid(form)
        else:
            messages.warning(self.request, _("You haven't made any changes."))
            return redirect(self.get_success_url())


@api_view(['GET'])
def setup_intent(request, organizer):
    try:
        stripe_customer_id = get_stripe_customer_id(organizer)
        payment_method_info = get_payment_method_info(stripe_customer_id)
        client_secret = create_setup_intent(stripe_customer_id)

        return Response(
            {
                'client_secret': client_secret,
                'stripe_public_key': get_stripe_publishable_key(),
                'payment_method_info': payment_method_info,
            }
        )
    except ValidationError as e:
        logger.error('Validation error creating setup intent: %s', str(e))
        return Response({'error': str(e)}, status=400)


@api_view(['POST'])
def save_payment_information(request, organizer):
    setup_intent_id = request.data.get('setup_intent_id')
    try:
        stripe_customer_id = get_stripe_customer_id(organizer)
        update_payment_info(setup_intent_id, stripe_customer_id)

        return Response(
            {
                'success': True,
            }
        )
    except ValidationError as e:
        logger.error('Validation error updating payment information: %s', str(e))
        return Response({'error': str(e)}, status=400)
