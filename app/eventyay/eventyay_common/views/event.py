import datetime as dt
import logging
import os
import re
import smtplib
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from urllib.parse import urlparse

from python_http_client.exceptions import HTTPError

import jwt
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Case, F, Max, Min, Prefetch, Q, Sum, When, IntegerField
from django.db.models.functions import Coalesce, Greatest
from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import iri_to_uri
from django.utils.functional import cached_property
from django.utils.timezone import get_current_timezone_name
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, ListView, TemplateView
from django_scopes import scope
from zoneinfo import ZoneInfo
from rest_framework import views
from django.views import View
from django.apps import apps

from eventyay.timezones import localize_datetime

from eventyay.base.i18n import language
from eventyay.base.gmail.errors import (
    GmailDailyLimitError,
    GmailPermanentError,
    GmailRateLimitError,
    GmailTemporaryError,
)
from eventyay.base.meetup import (
    PRIVACY_PRIVATE,
    get_rsvp_product_and_quota,
    get_video_config_initial,
    is_meetup_event,
    provision_meetup_event,
)
from eventyay.base.models import Event, EventMetaValue, GlobalPluginConfig, Organizer, Quota
from eventyay.base.services.notifications import notify_organizer_followers
from eventyay.base.models.cfp import default_fields
from eventyay.consts import DEFAULT_PLUGINS
from eventyay.base.services import tickets
from eventyay.base.settings import (
    DEFAULTS,
    SETTINGS_AFFECTING_CSS,
    is_event_series_creation_enabled,
    is_meetup_creation_enabled,
)
from eventyay.presale.style import regenerate_css
from eventyay.common.text.path import resolve_media_path
from eventyay.base.services.quotas import QuotaAvailability
from eventyay.control.forms.event import (
    EventWizardBasicsForm,
    EventWizardCopyForm,
    EventWizardFoundationForm,
    MeetupEventWizardBasicsForm,
)
from eventyay.control.forms.filter import EventFilterForm
from eventyay.control.permissions import EventPermissionRequiredMixin
from eventyay.control.views import PaginationMixin, UpdateView
from eventyay.control.views.event import DecoupleMixin, EventSettingsViewMixin, EventPlugins as ControlEventPlugins
from eventyay.control.views.product import MetaDataEditorMixin
from eventyay.eventyay_common.forms.event import EventCommonSettingsForm
from eventyay.eventyay_common.utils import (
    EventCreatedFor,
    check_create_permission,
)
from eventyay.orga.forms.email import CentralMailSettingsForm
from eventyay.orga.forms.event import EventFooterLinkFormset, EventHeaderLinkFormset
from eventyay.helpers.plugin_enable import is_video_enabled
from eventyay.multidomain.urlreverse import build_absolute_uri
from ..forms.event import EventCloneForm, EventUpdateForm

logger = logging.getLogger(__name__)


class EventList(PaginationMixin, ListView):
    model = Event
    context_object_name = 'events'
    template_name = 'eventyay_common/events/index.html'
    ordering_fields = [
        'name',
        'slug',
        'organizer',
        'date_from',
        'date_to',
        'total_quota',
        'live',
        'order_from',
        'order_to',
    ]

    def get_queryset(self):
        query_set = self.request.user.get_events_with_any_permission(self.request).prefetch_related(
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

        query_set = query_set.annotate(
            min_from=Min('subevents__date_from'),
            max_from=Max('subevents__date_from'),
            max_to=Max('subevents__date_to'),
            max_fromto=Greatest(Max('subevents__date_to'), Max('subevents__date_from')),
            total_quota=Sum(
                Case(When(quotas__subevent__isnull=True, then='quotas__size'), default=0, output_field=IntegerField())
            ),
        ).annotate(
            order_from=Coalesce('min_from', 'date_from'),
            order_to=Coalesce('max_fromto', 'max_to', 'max_from', 'date_to', 'date_from'),
        )

        ordering = self.request.GET.get('ordering')
        if ordering and ordering.lstrip('-') in self.ordering_fields:
            if ordering == 'date_from':
                query_set = query_set.order_by('order_from')
            elif ordering == '-date_from':
                query_set = query_set.order_by('-order_from')
            elif ordering == 'date_to':
                query_set = query_set.order_by('order_to')
            elif ordering == '-date_to':
                query_set = query_set.order_by('-order_to')
            else:
                query_set = query_set.order_by(ordering)
        else:
            query_set = query_set.order_by('-date_from')

        query_set = query_set.prefetch_related(
            Prefetch(
                'quotas',
                queryset=Quota.objects.filter(subevent__isnull=True).annotate(s=Coalesce(F('size'), 0)).order_by('-s'),
                to_attr='first_quotas',
            )
        )

        if self.filter_form.is_valid():
            query_set = self.filter_form.filter_qs(query_set)
        return query_set

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form

        quotas = []
        for s in ctx['events']:
            s.plugins_array = s.get_plugins()
            s.first_quotas = s.first_quotas[:4]
            quotas += list(s.first_quotas)

        qa = QuotaAvailability(early_out=False)
        for q in quotas:
            qa.queue(q)
        qa.compute()

        for q in quotas:
            q.cached_avail = qa.results[q]
            q.cached_availability_paid_orders = qa.count_paid_orders.get(q, 0)
            if q.size is not None:
                q.percent_paid = min(
                    100,
                    (round(q.cached_availability_paid_orders / q.size * 100) if q.size > 0 else 100),
                )
        ctx['event_series_creation_enabled'] = is_event_series_creation_enabled(self.request)
        ctx['meetup_creation_enabled'] = is_meetup_creation_enabled(self.request)
        return ctx

    @cached_property
    def filter_form(self):
        return EventFilterForm(data=self.request.GET, request=self.request)


class EventCreateView(TemplateView):
    template_name = 'eventyay_common/events/create.html'
    legacy_session_key = 'event_create_legacy_wizard_data'

    def get_template_names(self):
        if self.is_meetup_request:
            return ['eventyay_common/events/meetup_create.html']
        return [self.template_name]

    def get_create_organizer_queryset(self):
        queryset = Organizer.objects.all()
        if not self.request.user.has_active_staff_session(self.request.session.session_key):
            queryset = queryset.filter(
                id__in=self.request.user.teams.filter(can_create_events=True).values_list('organizer', flat=True)
            )
        return queryset

    def get_fallback_organizer(self):
        queryset = self.get_create_organizer_queryset()
        if self.request.user.is_authenticated:
            default_org = self.request.user.get_default_organizer(can_create_events=True)
            if default_org and queryset.filter(pk=default_org.pk).exists():
                return default_org
        return queryset.first()

    def get_organizer_slug_options(self):
        return {
            str(organizer.pk): {
                'prefix': build_absolute_uri(organizer, 'presale:organizer.index'),
                'rngUrl': reverse('control:events.add.slugrng', kwargs={'organizer': organizer.slug}),
            }
            for organizer in self.get_create_organizer_queryset()
        }

    def get_clone_queryset(self):
        return EventWizardCopyForm.copy_from_queryset(self.request.user, self.request.session)

    def get_foundation_initial(self):
        initial_form = {}
        request_get = self.request.GET

        initial_form['is_video_creation'] = True
        if request_get.get('meetup') == '1':
            initial_form['is_video_creation'] = False
            initial_form['is_meetup'] = True
        initial_form['locales'] = ['en']
        initial_form['create_for'] = EventCreatedFor.BOTH.value
        initial_form['has_subevents'] = request_get.get('series') == '1'
        queryset = self.get_create_organizer_queryset()
        if 'organizer' in request_get:
            try:
                initial_form['organizer'] = queryset.get(slug=request_get.get('organizer'))
            except Organizer.DoesNotExist:
                pass
        elif queryset.count() == 1:
            initial_form['organizer'] = queryset.first()
        elif self.request.user.is_authenticated:
            default_org = self.request.user.get_default_organizer(can_create_events=True)
            if default_org and queryset.filter(pk=default_org.pk).exists():
                initial_form['organizer'] = default_org
            elif queryset.exists():
                initial_form['organizer'] = queryset.first()

        return initial_form

    def get_basics_initial(self, foundation_data=None):
        if foundation_data is None:
            foundation_data = {}

        clone_from = self.clone_from
        initial_form = {}
        if clone_from:
            initial_form.update(
                {
                    'name': clone_from.name,
                    'date_from': clone_from.date_from,
                    'date_to': clone_from.date_to,
                    'presale_start': clone_from.presale_start,
                    'presale_end': clone_from.presale_end,
                    'location': clone_from.location,
                    'geo_lat': clone_from.geo_lat,
                    'geo_lon': clone_from.geo_lon,
                    'email': clone_from.email,
                    'timezone': clone_from.settings.get('timezone') or clone_from.timezone,
                    'locale': clone_from.settings.get('locale') or clone_from.locale,
                }
            )
            if is_meetup_event(clone_from):
                initial_form.update(get_video_config_initial(clone_from))
        else:
            initial_form['locale'] = 'en'

            # Set default dates: 3 months from now, 9 AM to 5 PM in user's timezone
            user_tz = ZoneInfo(get_current_timezone_name())
            now = datetime.now(user_tz)
            default_start = now + timedelta(days=90)
            default_start = default_start.replace(hour=9, minute=0, second=0, microsecond=0)
            default_end = default_start.replace(hour=17, minute=0, second=0, microsecond=0)

            initial_form['date_from'] = default_start
            initial_form['date_to'] = default_end

            # Set default timezone to user's system timezone (consistent with manual entry)
            initial_form['timezone'] = get_current_timezone_name()

        locales = foundation_data.get('locales') or self.get_foundation_initial().get('locales') or ['en']
        if initial_form.get('locale') not in locales:
            initial_form['locale'] = locales[0]

        return initial_form

    @cached_property
    def clone_from(self):
        if hasattr(self, '_clone_from'):
            return self._clone_from
        if self.request.GET.get('clone'):
            try:
                return self.get_clone_queryset().get(pk=self.request.GET.get('clone'))
            except Event.DoesNotExist:
                pass
        return None

    @property
    def is_meetup_request(self):
        return bool(
            self.request.GET.get('meetup') == '1'
            or self.request.POST.get('is_meetup') == 'on'
            or is_meetup_event(self.clone_from)
        )

    def dispatch(self, request, *args, **kwargs):
        is_series = request.GET.get('series') == '1' or request.POST.get('has_subevents') == 'on'
        if is_series and not is_event_series_creation_enabled(request):
            raise PermissionDenied(_('Event series creation is currently disabled.'))
        if self.is_meetup_request:
            if not is_meetup_creation_enabled(request):
                raise PermissionDenied(_('Meetup creation is currently disabled.'))
            if not self.get_create_organizer_queryset().exists():
                raise PermissionDenied(_('You do not have permission to create meetup events.'))
        return super().dispatch(request, *args, **kwargs)

    def get_foundation_form(self):
        return EventWizardFoundationForm(
            data=self.request.POST if self.request.method == 'POST' else None,
            initial=self.get_foundation_initial(),
            prefix='foundation',
            user=self.request.user,
            session=self.request.session,
        )

    def get_basics_form(self, foundation_data=None, bind=True):
        if foundation_data is None:
            foundation_data = self.get_foundation_initial()
        organizer = foundation_data.get('organizer') or self.get_fallback_organizer()
        form_class = MeetupEventWizardBasicsForm if self.is_meetup_request else EventWizardBasicsForm
        return form_class(
            data=self.request.POST if bind and self.request.method == 'POST' else None,
            files=self.request.FILES if bind and self.request.method == 'POST' else None,
            initial=self.get_basics_initial(foundation_data),
            prefix='basics',
            user=self.request.user,
            session=self.request.session,
            organizer=organizer,
            has_subevents=foundation_data.get('has_subevents', False),
            locales=foundation_data.get('locales') or ['en'],
            content_locales=foundation_data.get('content_locales'),
            is_video_creation=foundation_data.get('is_video_creation', True),
            restrict_locale_choices=False,
        )


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        foundation_form = kwargs.get('foundation_form') or self.get_foundation_form()
        foundation_data = foundation_form.cleaned_data if foundation_form.is_bound and foundation_form.is_valid() else None
        organizer = foundation_data.get('organizer') if foundation_data else foundation_form.initial.get('organizer')
        has_organizer = self.get_create_organizer_queryset().exists()
        basics_form = kwargs.get('basics_form')
        if has_organizer and basics_form is None:
            basics_form = self.get_basics_form(foundation_data)
        if basics_form and not organizer:
            basics_form.fields['slug'].widget.prefix = ''

        context['foundation_form'] = foundation_form
        context['basics_form'] = basics_form
        context['create_for'] = EventCreatedFor.BOTH.value
        context['has_organizer'] = has_organizer
        context['organizer'] = organizer
        context['organizer_slug_options'] = self.get_organizer_slug_options()
        context['organizer_slug_rng_url'] = (
            reverse('control:events.add.slugrng', kwargs={'organizer': organizer.slug}) if organizer else ''
        )
        context['event_creation_for_choice'] = {e.name: e.value for e in EventCreatedFor}
        context['clone_from'] = self.clone_from
        context['event_series_creation_enabled'] = is_event_series_creation_enabled(self.request)
        context['meetup_creation_enabled'] = is_meetup_creation_enabled(self.request)
        context['type_preselected'] = 'series' in self.request.GET
        context['is_meetup'] = self.is_meetup_request
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('ajax') == 'event-i18n-fields':
            return self.render_event_i18n_fields()

        if 'event_wizard-current_step' in request.POST:
            return self.post_legacy_wizard(request)

        foundation_form = self.get_foundation_form()
        foundation_valid = foundation_form.is_valid()
        foundation_data = foundation_form.cleaned_data if foundation_valid else {}
        basics_form = self.get_basics_form(foundation_data)

        if foundation_valid and basics_form.is_valid():
            return self.create_event(foundation_form, basics_form)

        messages.error(self.request, _('We could not create the event. See below for details.'))
        return self.render_to_response(
            self.get_context_data(foundation_form=foundation_form, basics_form=basics_form)
        )

    def render_event_i18n_fields(self):
        if not self.get_create_organizer_queryset().exists():
            return JsonResponse({'error': _('You cannot create events for any organizer.')}, status=403)

        valid_locale_codes = {code for code, _name in settings.LANGUAGES}
        locales = [
            locale for locale in self.request.POST.getlist('foundation-locales') if locale in valid_locale_codes
        ]
        if not locales:
            return JsonResponse({'error': _('Select at least one active language.')}, status=400)

        basics_form = self.get_basics_form({'locales': locales}, bind=False)
        for field_name in ('name', 'location'):
            values = {
                locale: self.request.POST.get(f'basics-{field_name}_{index}', '')
                for index, (locale, _name) in enumerate(settings.LANGUAGES)
                if f'basics-{field_name}_{index}' in self.request.POST
            }
            if values:
                basics_form.initial[field_name] = values
        fields = render_to_string(
            'eventyay_common/events/fragment_event_i18n_fields.html',
            {'basics_form': basics_form},
            request=self.request,
        )
        return JsonResponse({'fields': fields})

    def post_legacy_wizard(self, request):
        step = request.POST.get('event_wizard-current_step')
        if step == 'foundation':
            foundation_form = self.get_foundation_form()
            if foundation_form.is_valid():
                request.session[self.legacy_session_key] = {'foundation': self.serialize_post_data(request.POST)}
                basics_form = self.get_basics_form(foundation_form.cleaned_data)
                return self.render_to_response(
                    self.get_context_data(foundation_form=foundation_form, basics_form=basics_form)
                )
            return self.render_to_response(
                self.get_context_data(foundation_form=foundation_form, basics_form=self.get_basics_form({}))
            )

        legacy_data = request.session.get(self.legacy_session_key, {})
        foundation_post = legacy_data.get('foundation')
        if not foundation_post:
            return redirect(request.path)

        foundation_form = EventWizardFoundationForm(
            data=foundation_post,
            initial=self.get_foundation_initial(),
            prefix='foundation',
            user=self.request.user,
            session=self.request.session,
        )
        if not foundation_form.is_valid():
            return self.render_to_response(
                self.get_context_data(foundation_form=foundation_form, basics_form=self.get_basics_form({}))
            )

        if step == 'basics':
            basics_form = self.get_basics_form(foundation_form.cleaned_data)
            if basics_form.is_valid():
                legacy_data['basics'] = self.serialize_post_data(request.POST)
                request.session[self.legacy_session_key] = legacy_data
            return self.render_to_response(
                self.get_context_data(foundation_form=foundation_form, basics_form=basics_form)
            )

        if step == 'copy':
            basics_post = legacy_data.get('basics')
            if not basics_post:
                return redirect(request.path)
            basics_form_class = MeetupEventWizardBasicsForm if self.is_meetup_request else EventWizardBasicsForm
            basics_form = basics_form_class(
                data=basics_post,
                initial=self.get_basics_initial(foundation_form.cleaned_data),
                prefix='basics',
                user=self.request.user,
                session=self.request.session,
                organizer=foundation_form.cleaned_data['organizer'],
                has_subevents=foundation_form.cleaned_data.get('has_subevents', False),
                locales=foundation_form.cleaned_data.get('locales') or ['en'],
                content_locales=foundation_form.cleaned_data.get('content_locales'),
                is_video_creation=foundation_form.cleaned_data.get('is_video_creation', True),
                restrict_locale_choices=False,
            )
            copy_from_event = request.POST.get('copy-copy_from_event')
            if copy_from_event:
                try:
                    self._clone_from = self.get_clone_queryset().get(pk=copy_from_event)
                except Event.DoesNotExist:
                    self._clone_from = None
            if basics_form.is_valid():
                request.session.pop(self.legacy_session_key, None)
                return self.create_event(foundation_form, basics_form)
            return self.render_to_response(
                self.get_context_data(foundation_form=foundation_form, basics_form=basics_form)
            )

        return redirect(request.path)

    @staticmethod
    def serialize_post_data(post_data):
        return {
            key: values if len(values) > 1 else values[0]
            for key, values in ((key, post_data.getlist(key)) for key in post_data)
        }

    def create_event(self, foundation_form, basics_form):
        foundation_data = foundation_form.cleaned_data
        basics_data = basics_form.cleaned_data
        self.request.organizer = foundation_data['organizer']
        has_permission = check_create_permission(self.request)
        final_is_video_creation = foundation_data.get('is_video_creation', True) and has_permission

        # Derive the default locale: use whatever the form provides (set by the
        # hidden input that JS syncs from the language-order tray), but always fall
        # back to the first selected locale so the UI change is backward-compatible.
        locales_list = foundation_data['locales']
        chosen_locale = basics_data.get('locale') or (locales_list[0] if locales_list else 'en')
        if chosen_locale not in locales_list and locales_list:
            chosen_locale = locales_list[0]

        with transaction.atomic(), language(chosen_locale):
            event = basics_form.instance
            event.organizer = foundation_data['organizer']

            default_plugins = list(settings.EVENTYAY_PLUGINS_DEFAULT)
            global_default_plugins = GlobalPluginConfig.get_default_enabled_modules()

            ticketing_plugins = [
                'eventyay.plugins.banktransfer',
                'eventyay.plugins.manualpayment',
            ]

            installed_apps = {app.name for app in apps.get_app_configs()}

            for plugin_name in ['eventyay_stripe', 'eventyay_paypal']:
                if plugin_name in installed_apps:
                    ticketing_plugins.append(plugin_name)

            all_plugins = list(dict.fromkeys(default_plugins + global_default_plugins + ticketing_plugins))
            globally_disabled = GlobalPluginConfig.get_disabled_modules()
            all_plugins = [m for m in all_plugins if m not in globally_disabled]
            event.plugins = ','.join(all_plugins)

            event.has_subevents = foundation_data['has_subevents']
            event.is_video_creation = final_is_video_creation
            event.testmode = False
            event.private_testmode = False
            basics_form.save()
            if self.clone_from:
                event.clone_from(self.clone_from, new_secrets=True)
                event.copy_data_from(self.clone_from)

            with scope(organizer=event.organizer):
                event.checkin_lists.create(name=_('Default'), all_products=True)
                for team in self.request.user.teams.filter(organizer=event.organizer):
                    if not team.all_events and team.can_create_events:
                        team.limit_events.add(event)
            event.set_defaults()
            event.settings.set('timezone', basics_data['timezone'])
            content_locales = foundation_data.get('content_locales') or foundation_data['locales']
            event.update_language_configuration(
                locales=foundation_data['locales'],
                content_locales=content_locales,
                default_locale=chosen_locale,
            )
            event.refresh_from_db()
            cfp = event.cfp
            if 'content_locale' not in cfp.fields:
                cfp.fields['content_locale'] = default_fields()['content_locale'].copy()
            if len(foundation_data['locales']) > 1:
                cfp.fields['content_locale']['visibility'] = 'required'
                cfp.fields['content_locale']['public'] = True
            else:
                cfp.fields['content_locale']['visibility'] = 'do_not_ask'
                cfp.fields['content_locale']['public'] = False
            cfp.save(update_fields=['fields'])
            # Persist timezone on the event model as well so downstream consumers see the updated value
            event.timezone = basics_data['timezone']
            event.save(update_fields=['timezone', 'locale_array', 'content_locale_array'])

            # Use the selected create_for option, but ensure smart defaults work for all
            create_for = EventCreatedFor.BOTH.value
            event.settings.set('create_for', create_for)



            event.log_action(
                    action='eventyay.event.added',
                    user=self.request.user,
                )

            if self.is_meetup_request:
                crop_box = None
                try:
                    crop_x = int(float(self.request.POST.get('basics-logo_image_crop_x', '')))
                    crop_y = int(float(self.request.POST.get('basics-logo_image_crop_y', '')))
                    crop_w = int(float(self.request.POST.get('basics-logo_image_crop_w', '')))
                    crop_h = int(float(self.request.POST.get('basics-logo_image_crop_h', '')))
                    if crop_w > 0 and crop_h > 0 and crop_x >= 0 and crop_y >= 0:
                        crop_box = (crop_x, crop_y, crop_x + crop_w, crop_y + crop_h)
                except (OverflowError, ValueError, TypeError):
                    crop_box = None

                is_private = basics_data.get('privacy_type') == PRIVACY_PRIVATE
                provision_meetup_event(
                    event,
                    video_type=basics_data.get('video_type', ''),
                    video_url=basics_data.get('video_url', ''),
                    request=self.request,
                    frontpage_text=basics_data.get('frontpage_text'),
                    header_image=basics_form.cleaned_data.get('logo_image'),
                    registration_limit=basics_data.get('registration_limit'),
                    crop_box=crop_box,
                    registration_fee=basics_data.get('registration_fee'),
                    payment_stripe_publishable_key=basics_data.get('payment_stripe_publishable_key', ''),
                    payment_stripe_secret_key=basics_data.get('payment_stripe_secret_key', ''),
                    payment_stripe_merchant_country=basics_data.get('payment_stripe_merchant_country', ''),
                    is_private=is_private,
                )

        return redirect(
            reverse(
                'eventyay_common:event.index',
                kwargs={'event': event.slug, 'organizer': event.organizer.slug},
            )
        )


class EventUpdate(
    DecoupleMixin,
    EventSettingsViewMixin,
    EventPermissionRequiredMixin,
    MetaDataEditorMixin,
    UpdateView,
):
    model = Event
    form_class = EventUpdateForm
    template_name = 'eventyay_common/event/settings.html'
    permission = 'can_change_event_settings'

    class ValidComponentAction(StrEnum):
        ENABLE = 'enable'

    @cached_property
    def object(self) -> Event:
        return self.request.event

    def get_object(self, queryset=None) -> Event:
        return self.object

    @cached_property
    def sform(self):
        return EventCommonSettingsForm(
            obj=self.object,
            prefix='settings',
            data=self.request.POST if self.request.method == 'POST' else None,
            files=self.request.FILES if self.request.method == 'POST' else None,
        )

    @cached_property
    def email_form(self):
        return CentralMailSettingsForm(
            obj=self.object,
            attribute_name='settings',
            prefix='email',
            data=self.request.POST if self.request.method == 'POST' else None,
        )

    @cached_property
    def header_links_formset(self):
        return EventHeaderLinkFormset(
            self.request.POST if self.request.method == 'POST' else None,
            event=self.object,
            prefix='header-links',
            instance=self.object,
        )

    @cached_property
    def footer_links_formset(self):
        return EventFooterLinkFormset(
            self.request.POST if self.request.method == 'POST' else None,
            event=self.object,
            prefix='footer-links',
            instance=self.object,
        )

    def get_context_data(self, *args, **kwargs) -> dict:
        context = super().get_context_data(*args, **kwargs)
        context['sform'] = self.sform
        context['email_form'] = self.email_form
        context['renderers'] = self.object.get_html_mail_renderers()
        context['header_links_formset'] = self.header_links_formset
        context['footer_links_formset'] = self.footer_links_formset
        context['is_video_enabled'] = is_video_enabled(self.object)
        context['is_meetup_event'] = is_meetup_event(self.object)
        context['is_talk_event_created'] = False
        from eventyay.base.gmail.models import GmailOAuthCredential

        context['gmail_migration_pending'] = not GmailOAuthCredential.is_table_available()
        context['gmail_credential'] = GmailOAuthCredential.get_active_for_event_safe(self.object)
        gmail_kwargs = {'organizer': self.object.organizer.slug, 'event': self.object.slug}
        context['gmail_callback_url'] = self.request.build_absolute_uri(
            reverse('eventyay_common:event.gmail.callback', kwargs=gmail_kwargs)
        )
        context['gmail_connect_url'] = reverse('eventyay_common:event.gmail.connect', kwargs=gmail_kwargs)
        context['gmail_disconnect_url'] = reverse('eventyay_common:event.gmail.disconnect', kwargs=gmail_kwargs)
        if (
            self.object.settings.create_for == EventCreatedFor.BOTH
            or self.object.settings.talk_schedule_public is not None
        ):
            # Ignore case Event is created only for Talk as it not enable yet.
            context['is_talk_event_created'] = True
            
        
        return context

    def _run_email_test(self):
        """Test the central SMTP/SendGrid configuration and add a flash message."""
        event = self.object
        if not event.settings.smtp_use_custom:
            messages.error(self.request, _('Custom email gateway is not enabled.'))
            return
        vendor = event.settings.get('email_vendor', 'smtp')
        if vendor == 'gmail_api':
            from eventyay.base.gmail.models import GmailOAuthCredential

            if not GmailOAuthCredential.get_active_for_event(event):
                messages.error(
                    self.request,
                    _('Gmail is selected but no account is connected. Connect Gmail in the email settings first.'),
                )
                return
        elif vendor == 'sendgrid' and not event.settings.get('send_grid_api_key'):
            messages.error(self.request, _('SendGrid API key is missing. Please configure it and save.'))
            return
        if vendor != 'sendgrid' and vendor != 'gmail_api' and (not event.settings.get('smtp_host') or not event.settings.get('smtp_port')):
            messages.error(self.request, _('SMTP host or port is missing. Please configure them and save.'))
            return

        test_email = self.email_form.cleaned_data.get('test_email')
        to_addrs = [a.strip() for a in test_email.split(',') if a.strip()] if test_email else None
        backend = event.get_mail_backend(force_custom=True, timeout=10)
        try:
            backend.test(event.settings.mail_from, to_addrs=to_addrs)
        except UnicodeEncodeError:
            logger.warning('Central email test failed — non-ASCII characters (event=%s)', event.slug)
            messages.error(
                self.request,
                _('Email test failed because a field (password, username, or recipient) contains a non-ASCII character.'),
            )
        except HTTPError as e:
            logger.exception('Central SendGrid test failed (event=%s)', event.slug)
            messages.error(
                self.request,
                _('SendGrid test failed with HTTP error %(code)s. Check your API key and try again.')
                % {'code': e.response.status_code if hasattr(e, 'response') and e.response is not None else '?'},
            )
        except (GmailRateLimitError, GmailTemporaryError) as e:
            messages.warning(
                self.request,
                _('Gmail test email is temporarily delayed because of rate limits: %(err)s') % {'err': e},
            )
        except (GmailDailyLimitError, GmailPermanentError) as e:
            messages.error(
                self.request,
                _('Gmail test email could not be sent: %(err)s') % {'err': e},
            )
        except (smtplib.SMTPException, OSError):
            logger.exception('Central SMTP test failed (event=%s)', event.slug)
            messages.warning(
                self.request,
                _('Test email could not be delivered. Check the SMTP host, port, and credentials and try again.'),
            )
        else:
            messages.success(self.request, _('Test email sent successfully.'))

    @transaction.atomic
    def form_valid(self, form):
        self._save_decoupled(self.sform)
        self.sform.save()
        if any(k.startswith('email-') for k in self.request.POST):
            self.email_form.save()
        self.header_links_formset.save()
        self.footer_links_formset.save()
        # Keep event model timezone in sync with settings
        if 'timezone' in self.sform.cleaned_data:
            self.object.timezone = self.sform.cleaned_data['timezone']
            self.object.save(update_fields=['timezone'])
        form.instance.update_language_configuration(
            locales=self.sform.cleaned_data.get('locales'),
            default_locale=self.sform.cleaned_data.get('locale'),
        )

        tickets.invalidate_cache.apply_async(kwargs={'event': self.request.event.pk})

        if self.sform.has_changed():
            self.request.event.log_action(
                'eventyay.event.settings',
                user=self.request.user,
                data={k: self.request.event.settings.get(k) for k in self.sform.changed_data},
            )

        has_updates = any(
            (
                form.has_changed(),
                self.sform.has_changed(),
                self.email_form.has_changed(),
                self.header_links_formset.has_changed(),
                self.footer_links_formset.has_changed(),
            )
        )

        if self.request.POST.get('test', '0').strip() == '1':
            self._run_email_test()
        elif self.sform.has_changed() and any(p in self.sform.changed_data for p in SETTINGS_AFFECTING_CSS):
            transaction.on_commit(lambda: regenerate_css.apply_async(args=(self.request.event.pk,)))
            messages.success(
                self.request,
                _(
                    'Your changes have been saved. Please note that it can '
                    'take a short period of time until your changes become '
                    'active.'
                ),
            )
        elif has_updates:
            messages.success(self.request, _('Your changes have been saved.'))

        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse(
            'eventyay_common:event.update',
            kwargs={
                'organizer': self.object.organizer.slug,
                'event': self.object.slug,
            },
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pass necessary kwargs to the EventUpdateForm in common
        is_staff_session = self.request.user.has_active_staff_session(self.request.session.session_key)
        kwargs['change_slug'] = is_staff_session
        # TODO: Re-enable custom domain when unified system is stable
        # kwargs['domain'] = is_staff_session
        return kwargs

    def enable_talk_system(self, request: HttpRequest) -> bool:
        """
        Enable talk system for this event if it has not been created yet.
        """
        action = request.POST.get('enable_talk_system', '').lower()
        if action != self.ValidComponentAction.ENABLE:
            return False

        if not check_create_permission(self.request):
            messages.error(self.request, _('You do not have permission to perform this action.'))
            return False


        return True

    def enable_video_system(self, request: HttpRequest) -> bool:
        """
        Enable video system for this event if it has not been created yet.
        """
        action = request.POST.get('enable_video_system', '').lower()
        if action != self.ValidComponentAction.ENABLE:
            return False

        if not check_create_permission(self.request):
            messages.error(self.request, _('You do not have permission to perform this action.'))
            return False

        return True

    def post(self, request, *args, **kwargs):
        if request.POST.get('ajax') == 'delete_image':
            setting_key = request.POST.get('setting_key', '').strip()
            if not setting_key:
                field = request.POST.get('field', '').strip()
                if field.startswith('settings-'):
                    setting_key = field[len('settings-'):]
                else:
                    setting_key = field

            if setting_key in DEFAULTS and DEFAULTS[setting_key].get('type') is File:
                current_value = request.event.settings.get(setting_key, as_type=str)
                if current_value:
                    current_file = resolve_media_path(current_value)
                    if current_file and not str(current_file).startswith(('http://', 'https://')):
                        default_storage.delete(current_file)
                        base_path, unused_ext = os.path.splitext(current_file)
                        orig_ext = request.event.settings.get(f'{setting_key}_original_ext', as_type=str)
                        if orig_ext:
                            default_storage.delete(f'{base_path}_original.{orig_ext}')

                if request.event.settings.get(setting_key) is not None:
                    del request.event.settings[setting_key]
                orig_ext_key = f"{setting_key}_original_ext"
                if request.event.settings.get(orig_ext_key) is not None:
                    del request.event.settings[orig_ext_key]
                request.event.log_action('eventyay.event.settings.changed', user=request.user, data={setting_key: None})
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': 'Invalid field'}, status=400)

        if self.enable_talk_system(request):
            return redirect(self.get_success_url())

        if self.enable_video_system(request):
            return redirect(self.get_success_url())

        form = self.get_form()
        has_formset_changes = self.header_links_formset.has_changed() or self.footer_links_formset.has_changed()
        is_test_request = request.POST.get('test', '0').strip() == '1'
        has_email_form_data = any(k.startswith('email-') for k in request.POST)
        email_form_valid = (not has_email_form_data) or self.email_form.is_valid()
        if is_test_request or form.changed_data or self.sform.changed_data or self.email_form.has_changed() or has_formset_changes:
            form.instance.sales_channels = ['web']
            if (
                form.is_valid()
                and self.sform.is_valid()
                and email_form_valid
                and self.header_links_formset.is_valid()
                and self.footer_links_formset.is_valid()
            ):
                zone = ZoneInfo(self.sform.cleaned_data['timezone'])
                event = form.instance
                event.date_from = self.reset_timezone(zone, event.date_from)
                event.date_to = self.reset_timezone(zone, event.date_to)
                return self.form_valid(form)
            else:
                messages.error(
                    self.request,
                    _('We could not save your changes. See below for details.'),
                )
                return self.form_invalid(form)
        else:
            messages.warning(self.request, _("You haven't made any changes."))
            return HttpResponseRedirect(self.request.path)

    @staticmethod
    def reset_timezone(zone, dt):
        return localize_datetime(dt, zone)


class EventPlugins(ControlEventPlugins):
    template_name = 'eventyay_common/event/plugins.html'

    def get_success_url(self) -> str:
        return reverse(
            'eventyay_common:event.plugins',
            kwargs={
                'organizer': self.get_object().organizer.slug,
                'event': self.get_object().slug,
            },
        )


class EventLive(TemplateView):
    template_name = 'eventyay_common/event/live.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied(_('You do not have permission to view this content.'))
        can_change = request.user.has_event_permission(
            request.organizer,
            request.event,
            'can_change_event_settings',
            request=request,
        )
        if not (can_change or request.user.is_administrator):
            raise PermissionDenied(_('You do not have permission to view this content.'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['actual_orders'] = self.request.event.orders.filter(testmode=False).exists()
        ticketing_ready = self.request.event.products.exists() and self.request.event.quotas.exists()
        billing_issues = self.request.event.billing_issues()
        billing_issue_texts = {str(issue) for issue in billing_issues}
        ctx['ticketing_ready'] = ticketing_ready
        ctx['ticket_issues'] = (
            [issue for issue in self.request.event.live_issues if str(issue) not in billing_issue_texts]
            if ticketing_ready
            else []
        )
        ctx['info_publish_issues'] = billing_issues
        ctx['tickets_published'] = self.request.event.tickets_published
        ctx['talks_published'] = self.request.event.talks_published
        ctx['schedule_released'] = bool(self.request.event.current_schedule)
        private_tickets = self.request.event.settings.get('private_testmode_tickets', False, as_type=bool)
        private_talks = self.request.event.settings.get('private_testmode_talks', False, as_type=bool)
        if not self.request.event.private_testmode:
            private_tickets = False
            private_talks = False
        ctx['private_testmode_tickets'] = private_tickets
        ctx['private_testmode_talks'] = private_talks
        ctx['is_video_enabled'] = is_video_enabled(self.request.event)
        
        components_ready = 0
        if self.request.event.live:
            components_ready += 1
        if self.request.event.tickets_published:
            components_ready += 1
        if self.request.event.talks_published:
            components_ready += 1
        if ctx['is_video_enabled'] and self.request.event.settings.venueless_show_public_link:
            components_ready += 1
            
        ctx['setup_progress'] = components_ready
        ctx['setup_progress_percent'] = int((components_ready / 4) * 100)
        
        ctx['setup_progress_color'] = '#007bff'
        
        public_pages = []
        if self.request.event.live:
            public_pages.append(_('Info'))
            if self.request.event.tickets_published:
                public_pages.append(_('Tickets'))
            if self.request.event.talks_published:
                public_pages.append(_('CFP'))
            if ctx['schedule_released'] and self.request.event.talks_published:
                public_pages.append(_('Schedule / Sessions / Speakers'))
        ctx['public_pages'] = public_pages
        warnings = []
        suggestions = []
        if hasattr(self.request.event, 'cfp'):
            cfp = self.request.event.cfp
            if not cfp.text:
                warnings.append(
                    {
                        'text': _('The Call for Proposals text is missing. Please add a description.'),
                        'url': cfp.urls.text,
                    }
                )
            elif len(str(cfp.text)) < 50:
                warnings.append(
                    {
                        'text': _('The Call for Proposals text is too short (needs at least 50 characters).'),
                        'url': cfp.urls.text,
                    }
                )
            if (
                self.request.event.get_feature_flag('use_tracks')
                and cfp.request_track
                and self.request.event.tracks.count() < 2
            ):
                suggestions.append(
                    {
                        'text': _(
                            'You want submitters to choose the tracks for their proposals, but you do not offer tracks for selection. Add at least one track!'
                        ),
                        'url': cfp.urls.tracks,
                    }
                )
            if self.request.event.submission_types.count() == 1:
                suggestions.append(
                    {
                        'text': _('You have configured only one session type so far.'),
                        'url': cfp.urls.types,
                    }
                )
            if not self.request.event.talkquestions.exists():
                suggestions.append(
                    {
                        'text': _('You have configured no custom fields yet.'),
                        'url': cfp.urls.new_question,
                    }
                )
        ctx['warnings'] = warnings
        ctx['suggestions'] = suggestions
        return ctx

    def post(self, request, *args, **kwargs):
        event = request.event
        ticketing_ready = event.products.exists() and event.quotas.exists()
        billing_issue_texts = {str(issue) for issue in event.billing_issues()}
        ticket_issues = [issue for issue in event.live_issues if str(issue) not in billing_issue_texts]
        if request.POST.get('live') == 'true':
            if event.billing_issues():
                messages.error(
                    self.request,
                    _('Please resolve the billing information before publishing the event.'),
                )
                return redirect(self.request.path)
            with transaction.atomic():
                event.live = True
                event.save()
                self.request.event.log_action('eventyay.event.live.activated', user=self.request.user, data={})
                transaction.on_commit(lambda: notify_organizer_followers.apply_async(args=(event.pk,)))
            messages.success(self.request, _('Your event is now online.'))

        elif request.POST.get('live') == 'false':
            if event.tickets_published:
                messages.error(
                    self.request,
                    _('You cannot unpublish the event while tickets are published. Please switch ticketing to private test mode first.'),
                )
                return redirect(self.request.path)
            if event.talks_published:
                messages.error(
                    self.request,
                    _('You cannot unpublish the event while talks are published. Please switch talks to private test mode first.'),
                )
                return redirect(self.request.path)

            with transaction.atomic():
                event.live = False
                event.save()
                self.request.event.log_action('eventyay.event.live.deactivated', user=self.request.user, data={})
            messages.success(
                self.request,
                _('Your event has been unpublished.'),
            )

        elif request.POST.get('ticketing_mode'):
            mode = request.POST.get('ticketing_mode')
            if not ticketing_ready:
                messages.error(self.request, _('Please set up ticketing before changing ticket modes.'))
                return redirect(self.request.path)
            with transaction.atomic():
                previous_testmode = event.testmode
                previous_private = event.private_testmode
                if mode == 'private_test':
                    event.tickets_published = False
                    event.testmode = False
                    event.settings.private_testmode_tickets = True
                    event.private_testmode = True
                    messages.success(self.request, _('Private test mode is now enabled for tickets.'))
                elif mode == 'public_test':
                    if not event.live:
                        messages.error(self.request, _('Publish the event before testing tickets publicly.'))
                        return redirect(self.request.path)
                    event.tickets_published = True
                    event.settings.private_testmode_tickets = False
                    event.private_testmode = event.settings.get('private_testmode_talks', False, as_type=bool)
                    event.testmode = True
                    messages.success(self.request, _('Your shop is now in public test mode!'))
                elif mode == 'public_sales':
                    if not event.live:
                        messages.error(self.request, _('Publish the event before publishing tickets.'))
                        return redirect(self.request.path)
                    if ticket_issues:
                        messages.error(self.request, _('Please resolve the ticketing issues before publishing tickets.'))
                        return redirect(self.request.path)

                    if event.testmode and self.request.POST.get('delete_test_orders') == 'yes':
                        try:
                            with transaction.atomic():
                                for order in event.orders.filter(testmode=True):
                                    order.gracefully_delete(user=self.request.user)
                            event.cache.delete('complain_testmode_orders')
                        except ProtectedError:
                            messages.error(
                                self.request,
                                _(
                                    'An order could not be deleted as some constraints (e.g. data '
                                    'created by plug-ins) do not allow it.'
                                ),
                            )
                            return redirect(self.request.path)

                    event.tickets_published = True
                    event.settings.private_testmode_tickets = False
                    event.private_testmode = event.settings.get('private_testmode_talks', False, as_type=bool)
                    event.testmode = False
                    event.cartposition_set.filter(addon_to__isnull=False).delete()
                    event.cartposition_set.all().delete()
                    messages.success(self.request, _('Tickets are now publicly sold.'))
                else:
                    messages.error(self.request, _('Unknown ticketing mode.'))
                    return redirect(self.request.path)
                event.save()
                if previous_testmode != event.testmode:
                    self.request.event.log_action(
                        'eventyay.event.testmode.activated' if event.testmode else 'eventyay.event.testmode.deactivated',
                        user=self.request.user,
                        data={},
                    )
                if previous_private != event.private_testmode:
                    self.request.event.log_action(
                        'eventyay.event.private_testmode.activated' if event.private_testmode else 'eventyay.event.private_testmode.deactivated',
                        user=self.request.user,
                        data={},
                    )

        elif request.POST.get('talk_mode'):
            mode = request.POST.get('talk_mode')
            with transaction.atomic():
                previous_private = event.private_testmode
                if mode == 'private_test':
                    event.talks_published = False
                    event.settings.private_testmode_talks = True
                    event.settings.talks_testmode = False
                    event.private_testmode = True
                    messages.success(self.request, _('Private test mode is now enabled for talks.'))
                elif mode == 'public':
                    if not event.live:
                        messages.error(self.request, _('Publish the event before publishing talks.'))
                        return redirect(self.request.path)
                    event.talks_published = True
                    event.settings.private_testmode_talks = False
                    event.settings.talks_testmode = False
                    event.private_testmode = event.settings.get('private_testmode_tickets', False, as_type=bool)
                    messages.success(self.request, _('Talk pages are now published.'))
                else:
                    messages.error(self.request, _('Unknown talk mode.'))
                    return redirect(self.request.path)
                event.save()
                if previous_private != event.private_testmode:
                    self.request.event.log_action(
                        'eventyay.event.private_testmode.activated' if event.private_testmode else 'eventyay.event.private_testmode.deactivated',
                        user=self.request.user,
                        data={},
                    )

        elif request.POST.get('toggle_video_visibility') is not None:
            if not is_video_enabled(event):
                messages.error(self.request, _('Please configure video settings before changing visibility.'))
                return redirect(self.request.path)
            current_setting = event.settings.get('venueless_show_public_link', False)
            new_setting = not current_setting
            if new_setting and not event.live:
                messages.error(self.request, _('Publish the event before enabling public video link.'))
                return redirect(self.request.path)
            event.settings.set('venueless_show_public_link', new_setting)
            if new_setting:
                messages.success(self.request, _('Video link is now visible on public pages.'))
            else:
                messages.success(self.request, _('Video link is now hidden from public pages.'))
        return redirect(self.get_success_url())

    def get_success_url(self) -> str:
        return reverse(
            'eventyay_common:event.live',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


class VideoAccessAuthenticator(View):
    _RESUME_QUERY_SAFE = re.compile(r'^[a-zA-Z0-9_=&%.+-]*$')
    _RESUME_PATH_SEGMENT_SAFE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$')

    def get(self, request, *args, **kwargs):
        """
        Check if the video configuration is complete, the plugin is enabled, and the user has permission to modify the event settings.
        If configuration is missing, automatically set it up. Then redirect directly to the session-authenticated video organizer dashboard.
        @param request: user request
        @param args: arguments
        @param kwargs: keyword arguments
        @return: redirect to the video organizer dashboard
        """
        # Auto-setup video configuration if missing
        self._ensure_video_configuration()

        target = f'/video/event/{self.request.organizer.slug}/{self.request.event.slug}/'
        resume_suffix = self._resume_suffix_from_request(request)
        if resume_suffix:
            target = f"{target.rstrip('/')}/{resume_suffix.lstrip('/')}"
        return redirect(target)

    def _resume_suffix_from_request(self, request: HttpRequest) -> str | None:
        path = (request.GET.get('resume_path') or '').strip().strip('/')
        query = (request.GET.get('resume_query') or '').strip()
        if path or query:
            if not path:
                return None
            raw = f'{path}?{query}' if query else path
            return self._safe_video_resume_suffix(raw)
        legacy = request.GET.get('resume', '')
        return self._safe_video_resume_suffix(legacy) if legacy else None

    def _safe_video_resume_suffix(self, raw: str) -> str | None:
        """
        Path (and optional query) appended under the event video base URL after minting a token.
        Rejects absolute URLs, traversal, and odd encodings to avoid open redirects.
        """
        if not raw or not isinstance(raw, str):
            return None
        raw = raw.strip().strip('/')
        if not raw:
            return None
        if '#' in raw or any(ord(c) < 32 or ord(c) == 127 for c in raw):
            return None
        if raw.startswith(('/', '\\')) or '..' in raw or '//' in raw:
            return None
        path, sep, query = raw.partition('?')
        parts = [p for p in path.split('/') if p and p != '.']
        if any(p == '..' for p in parts):
            return None
        for p in parts:
            if not self._RESUME_PATH_SEGMENT_SAFE.fullmatch(p):
                return None
        if query and not self._RESUME_QUERY_SAFE.fullmatch(query):
            return None
        safe_path = '/'.join(parts)
        if not safe_path and not query:
            return None
        if query:
            return f'{safe_path}?{query}' if safe_path else None
        return safe_path

    def _ensure_video_configuration(self):
        """
        Ensure video configuration is set up properly, similar to admin token flow
        """
        event = self.request.event
        request = self.request

        # Ensure JWT configuration exists
        if not event.config or not event.config.get("JWT_secrets"):
            from django.utils.crypto import get_random_string

            secret = get_random_string(length=64)
            config = dict(event.config or {})
            config["JWT_secrets"] = [
                {
                    "issuer": "any",
                    "audience": "eventyay",
                    "secret": secret,
                }
            ]
            event.config = config
            event.save(update_fields=["config"])

        # Get or use existing JWT secret
        jwt_config = event.config["JWT_secrets"][0]
        secret = jwt_config["secret"]
        audience = jwt_config["audience"]
        issuer = jwt_config["issuer"]

        # Setup video plugin settings for the video frontend
        # Set each video config setting individually if missing
        if not event.settings.venueless_secret:
            event.settings.venueless_secret = secret
        if not event.settings.venueless_issuer:
            event.settings.venueless_issuer = issuer
        if not event.settings.venueless_audience:
            event.settings.venueless_audience = audience
        def build_video_url(host=None):
            scheme = 'https' if request.is_secure() else 'http'
            base_host = host or request.get_host()
            return f"{scheme}://{base_host}{event.urls.video_base}"

        if not event.settings.venueless_url:
            event.settings.venueless_url = build_video_url()
            logger.info(
                "Initialized video_url for event %s to %s",
                event.slug,
                event.settings.venueless_url,
            )
            return

        if not settings.DEBUG:
            return

        try:
            saved = urlparse(str(event.settings.venueless_url))
            current_host = request.get_host()
            if saved.netloc and saved.netloc != current_host:
                event.settings.venueless_url = build_video_url(current_host)
                logger.info(
                    "Adjusted video_url for event %s to %s",
                    event.slug,
                    event.settings.venueless_url,
                )
        except Exception:
            logger.exception(
                "Failed to parse video_url for event %s; falling back to current host.",
                event.slug,
            )
            event.settings.venueless_url = build_video_url()

        # Video is integrated; do not toggle event plugins here.


class EventSearchView(views.APIView):
    def get(self, request):
        query = request.GET.get('query', '')
        events = (
            Event.objects.filter(Q(name__icontains=query) | Q(slug__icontains=query))
            .order_by('name')
            .select_related('organizer')[:10]
        )

        results = []
        for event in events:
            if request.user.has_event_permission(event.organizer, event, 'can_view_orders', request=request):
                results.append({'name': event.name, 'slug': event.slug, 'organizer': event.organizer.slug})

        return JsonResponse(results, safe=False)


class EventCloneView(EventSettingsViewMixin, EventPermissionRequiredMixin, FormView):
    template_name = 'eventyay_common/event/clone.html'
    permission = 'can_change_event_settings'
    form_class = EventCloneForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('ajax') == 'event-i18n-fields':
            return self.render_event_i18n_fields()
        return super().post(request, *args, **kwargs)

    def render_event_i18n_fields(self):
        valid_locale_codes = {code for code, _name in settings.LANGUAGES}
        locales = [
            locale for locale in self.request.POST.getlist('locales') if locale in valid_locale_codes
        ]
        if not locales:
            from django.http import JsonResponse
            from django.utils.translation import gettext as _
            return JsonResponse({'error': _('Select at least one active language.')}, status=400)

        clone_from = self.request.event
        user_tz = ZoneInfo(get_current_timezone_name())
        now_dt = datetime.now(user_tz)
        default_start = now_dt + timedelta(days=90)
        default_start = default_start.replace(hour=9, minute=0, second=0, microsecond=0)
        default_end = default_start.replace(hour=17, minute=0, second=0, microsecond=0)

        initial = {
            'name': clone_from.name,
            'date_from': default_start,
            'date_to': default_end,
            'timezone': clone_from.settings.get('timezone') or clone_from.timezone,
            'locale': clone_from.settings.get('locale') or clone_from.locale,
            'locales': locales,
        }
        name_values = {}
        for index, locale in enumerate(locales):
            key = f'name_{index}'
            if key in self.request.POST:
                value = self.request.POST.get(key, '').strip()
                if value:
                    name_values[locale] = value
        if name_values:
            initial['name'] = name_values

        form = self.form_class(
            data=None,
            initial=initial,
            organizer=clone_from.organizer,
            locales=locales,
        )

        from django.template.loader import render_to_string
        from django.http import JsonResponse
        fields = render_to_string(
            'eventyay_common/event/fragment_event_clone_i18n_fields.html',
            {'form': form},
            request=self.request,
        )
        return JsonResponse({'fields': fields})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.event.organizer
        clone_from = self.request.event
        clone_locales = list(clone_from.settings.get('locales') or [clone_from.locale or 'en'])
        kwargs['locales'] = clone_locales
        user_tz = ZoneInfo(get_current_timezone_name())
        now_dt = datetime.now(user_tz)
        default_start = now_dt + timedelta(days=90)
        default_start = default_start.replace(hour=9, minute=0, second=0, microsecond=0)
        default_end = default_start.replace(hour=17, minute=0, second=0, microsecond=0)

        kwargs['initial'] = {
            'name': clone_from.name,
            'date_from': default_start,
            'date_to': default_end,
            'timezone': clone_from.settings.get('timezone') or clone_from.timezone,
            'locale': clone_from.settings.get('locale') or clone_from.locale,
            'locales': clone_locales,
            'clone_common_data': True,
            'clone_ticketing_data': True,
            'clone_talk_data': True,
        }
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organizer_slug_rng_url'] = reverse('control:events.add.slugrng', kwargs={'organizer': self.request.event.organizer.slug})
        return context

    def dispatch(self, request, *args, **kwargs):
        if not check_create_permission(request):
            raise PermissionDenied(_('You do not have permission to create events.'))
        return super().dispatch(request, *args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        old_event = self.request.event
        new_event = form.instance
        
        clone_options = {
            'clone_common_data': form.cleaned_data.get('clone_common_data'),
            'clone_settings': form.cleaned_data.get('clone_settings'),
            'clone_design_texts': form.cleaned_data.get('clone_design_texts'),
            'clone_email_settings': form.cleaned_data.get('clone_email_settings'),
            'clone_ticketing_data': form.cleaned_data.get('clone_ticketing_data'),
            'clone_products': form.cleaned_data.get('clone_products'),
            'clone_questions': form.cleaned_data.get('clone_questions'),
            'clone_checkin_lists': form.cleaned_data.get('clone_checkin_lists'),
            'clone_payment_settings': form.cleaned_data.get('clone_payment_settings'),
            'clone_talk_data': form.cleaned_data.get('clone_talk_data'),
            'clone_cfp': form.cleaned_data.get('clone_cfp'),
            'clone_session_types_tracks': form.cleaned_data.get('clone_session_types_tracks'),
            'clone_review_settings': form.cleaned_data.get('clone_review_settings'),
        }

        new_event.organizer = old_event.organizer
        if clone_options.get('clone_common_data') and clone_options.get('clone_settings'):
            new_event.plugins = old_event.plugins
        new_event.has_subevents = old_event.has_subevents
        new_event.is_video_creation = old_event.is_video_creation
        new_event.testmode = False
        new_event.private_testmode = False
        
        new_event.timezone = form.cleaned_data['timezone']
        new_event.locale = form.cleaned_data['locale']
        form.save()

        new_event.clone_from(old_event, new_secrets=True)
        new_event.copy_data_from(old_event, clone_options=clone_options)
        
        new_event.settings.set('locales', form.cleaned_data['locales'])
        
        if clone_options.get('clone_talk_data') and clone_options.get('clone_cfp', True) and getattr(old_event, 'cfp', None):
            new_event.cfp.copy_data_from(old_event.cfp)

        with scope(organizer=new_event.organizer):
            if not new_event.checkin_lists.exists():
                new_event.checkin_lists.create(name=_('Default'), all_products=True)
            for team in self.request.user.teams.filter(organizer=new_event.organizer):
                if not team.all_events and team.can_create_events:
                    team.limit_events.add(new_event)

        new_event.set_defaults()
        
        # Override the values potentially cloned from the old event to the ones chosen in the form
        new_event.timezone = form.cleaned_data['timezone']
        new_event.locale = form.cleaned_data['locale']
        new_event.save(update_fields=['timezone', 'locale'])
        new_event.settings.set('timezone', form.cleaned_data['timezone'])
        new_event.settings.set('locale', form.cleaned_data['locale'])
        
        cloned_locales = new_event.settings.get('locales', as_type=list) or []
        if form.cleaned_data['locale'] not in cloned_locales:
            cloned_locales.append(form.cleaned_data['locale'])
        new_event.settings.set('locales', cloned_locales)

        new_event.log_action(
            action='eventyay.event.added',
            user=self.request.user,
        )

        messages.success(self.request, _('Event has been cloned successfully.'))
        return redirect(
            reverse(
                'eventyay_common:event.update',
                kwargs={'event': new_event.slug, 'organizer': new_event.organizer.slug},
            )
        )
