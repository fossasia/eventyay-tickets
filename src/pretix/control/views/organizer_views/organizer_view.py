import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.db import transaction
from django.db.models import Max, Min, Prefetch, ProtectedError
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import (
    CreateView, DetailView, FormView, ListView, UpdateView,
)

from pretix.base.models.event import Event, EventMetaValue
from pretix.base.models.organizer import Organizer, OrganizerBillingModel, Team
from pretix.base.settings import SETTINGS_AFFECTING_CSS
from pretix.control.forms.filter import EventFilterForm, OrganizerFilterForm
from pretix.control.forms.organizer import OrganizerFooterLink
from pretix.control.forms.organizer_forms import (
    MailSettingsForm, OrganizerDeleteForm, OrganizerForm,
    OrganizerSettingsForm, OrganizerUpdateForm,
)
from pretix.control.permissions import (
    AdministratorPermissionRequiredMixin, OrganizerPermissionRequiredMixin,
)
from pretix.control.signals import nav_organizer
from pretix.control.views import PaginationMixin
from pretix.presale.style import regenerate_organizer_css

from ...forms.organizer_forms.organizer_form import BillingSettingsForm
from .organizer_detail_view_mixin import OrganizerDetailViewMixin

logger = logging.getLogger(__name__)


class OrganizerCreate(CreateView):
    model = Organizer
    form_class = OrganizerForm
    template_name = 'pretixcontrol/organizers/create.html'
    context_object_name = 'organizer'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_active_staff_session(self.request.session.session_key):
            raise PermissionDenied()  # TODO
        return super().dispatch(request, *args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, _('The new organizer has been created.'))
        ret = super().form_valid(form)
        t = Team.objects.create(
            organizer=form.instance, name=_('Administrators'),
            all_events=True, can_create_events=True, can_change_teams=True, can_manage_gift_cards=True,
            can_change_organizer_settings=True, can_change_event_settings=True, can_change_items=True,
            can_view_orders=True, can_change_orders=True, can_view_vouchers=True, can_change_vouchers=True
        )
        t.members.add(self.request.user)
        return ret

    def get_success_url(self) -> str:
        return reverse('control:organizer', kwargs={
            'organizer': self.object.slug,
        })


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
            files=self.request.FILES if self.request.method == 'POST' else None
        )

    def get_context_data(self, *args, **kwargs) -> dict:
        context = super().get_context_data(*args, **kwargs)
        context['sform'] = self.sform
        context['footer_links_formset'] = self.footer_links_formset
        return context

    @transaction.atomic
    def form_valid(self, form):
        self.sform.save()
        self.save_footer_links_formset(self.object)
        change_css = False
        if self.sform.has_changed():
            self.request.organizer.log_action(
                'pretix.organizer.settings',
                user=self.request.user,
                data={
                    k: (self.sform.cleaned_data.get(k).name
                        if isinstance(self.sform.cleaned_data.get(k), File)
                        else self.sform.cleaned_data.get(k))
                    for k in self.sform.changed_data
                }
            )
            if any(p in self.sform.changed_data for p in SETTINGS_AFFECTING_CSS):
                change_css = True
        if self.footer_links_formset.has_changed():
            self.request.organizer.log_action('eventyay.organizer.footerlinks.changed',
                                              user=self.request.user,
                                              data={
                                                  'data': self.footer_links_formset.cleaned_data
                                              })
        if form.has_changed():
            self.request.organizer.log_action(
                'pretix.organizer.changed',
                user=self.request.user,
                data={k: form.cleaned_data.get(k) for k in form.changed_data}
            )

        if change_css:
            regenerate_organizer_css.apply_async(args=(self.request.organizer.pk,))
            messages.success(self.request, _('Your changes have been saved. Please note that it can '
                                             'take a short period of time until your changes become '
                                             'active.'))
        else:
            messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.user.has_active_staff_session(self.request.session.session_key):
            kwargs['domain'] = True
            kwargs['change_slug'] = True
        return kwargs

    def get_success_url(self) -> str:
        return reverse('control:organizer.edit', kwargs={
            'organizer': self.request.organizer.slug,
        })

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid() and self.sform.is_valid() and self.footer_links_formset.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    @cached_property
    def footer_links_formset(self):
        return OrganizerFooterLink(self.request.POST if self.request.method == "POST" else None,
                                   organizer=self.object,
                                   prefix="footer-links",
                                   instance=self.object)

    def save_footer_links_formset(self, obj):
        self.footer_links_formset.save()


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
        try:
            with transaction.atomic():
                self.request.user.log_action(
                    'pretix.organizer.deleted', user=self.request.user,
                    data={
                        'organizer_id': self.request.organizer.pk,
                        'name': str(self.request.organizer.name),
                        'logentries': list(self.request.organizer.all_logentries().values_list('pk', flat=True))
                    }
                )
                self.request.organizer.delete_sub_objects()
                self.request.organizer.delete()
            messages.success(self.request, _('The organizer has been deleted.'))
            return redirect(self.get_success_url())
        except ProtectedError:
            messages.error(self.request,
                           _('The organizer could not be deleted as some constraints (e.g. data created by '
                             'plug-ins) do not allow it.'))
            return self.get(self.request, *self.args, **self.kwargs)

    def get_success_url(self) -> str:
        return reverse('control:index')


class OrganizerDisplaySettings(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, View):
    permission = None

    def get(self, request, *wargs, **kwargs):
        return redirect(reverse('control:organizer.edit', kwargs={
            'organizer': self.request.organizer.slug,
        }) + '#tab-0-3-open')


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
                    'pretix.organizer.settings', user=self.request.user, data={
                        k: (form.cleaned_data.get(k).name
                            if isinstance(form.cleaned_data.get(k), File)
                            else form.cleaned_data.get(k))
                        for k in form.changed_data
                    }
                )
            messages.success(self.request, _('Your changes have been saved.'))
            return redirect(self.get_success_url())
        else:
            messages.error(self.request, _('We could not save your changes. See below for details.'))
            return self.get(request)


class OrganizerMailSettings(OrganizerSettingsFormView):
    form_class = MailSettingsForm
    template_name = 'pretixcontrol/organizers/mail.html'
    permission = 'can_change_organizer_settings'

    def get_success_url(self):
        return reverse('control:organizer.settings.mail', kwargs={
            'organizer': self.request.organizer.slug,
        })

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        Handles POST requests to process the form, save changes, log actions, and test SMTP settings if requested.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: Redirects to the success URL if the form is valid, otherwise re-renders the form with errors.
        """
        form = self.get_form()

        if form.is_valid():
            form.save()

            if form.has_changed():
                self.request.organizer.log_action(
                    'pretix.organizer.settings', user=self.request.user, data={
                        k: form.cleaned_data.get(k) for k in form.changed_data
                    }
                )

            if request.POST.get('test', '0').strip() == '1':
                backend = self.request.organizer.get_mail_backend(force_custom=True, timeout=10)
                try:
                    backend.test(self.request.organizer.settings.mail_from)
                except Exception as e:
                    messages.warning(self.request, _('An error occurred while contacting the SMTP server: %s') % str(e))
                else:
                    success_message = _(
                        'Your changes have been saved and the connection attempt to your SMTP server was successful.') \
                        if form.cleaned_data.get('smtp_use_custom') else \
                        _('We\'ve been able to contact the SMTP server you configured. Remember to check '
                          'the "use custom SMTP server" checkbox, otherwise your SMTP server will not be used.')
                    messages.success(self.request, success_message)
            else:
                messages.success(self.request, _('Your changes have been saved.'))

            return redirect(self.get_success_url())

        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return self.get(request)


class OrganizerTeamView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DetailView):
    model = Organizer
    template_name = 'pretixcontrol/organizers/teams.html'
    permission = 'can_change_permissions'
    context_object_name = 'organizer'


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
        qs = self.request.user.get_events_with_any_permission(self.request).select_related(
            'organizer').prefetch_related(
            'organizer', '_settings_objects', 'organizer___settings_objects',
            'organizer__meta_properties',
            Prefetch(
                'meta_values',
                EventMetaValue.objects.select_related('property'),
                to_attr='meta_values_cached'
            )
        ).filter(organizer=self.request.organizer).order_by('-date_from')
        qs = qs.annotate(
            min_from=Min('subevents__date_from'),
            max_from=Max('subevents__date_from'),
            max_to=Max('subevents__date_to'),
            max_fromto=Greatest(Max('subevents__date_to'), Max('subevents__date_from'))
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
        ctx['meta_fields'] = [
            self.filter_form['meta_{}'.format(p.name)] for p in self.organizer.meta_properties.all()
        ]
        return ctx


class OrganizerDetailViewMixin:
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['nav_organizer'] = []
        ctx['organizer'] = self.request.organizer

        for recv, retv in nav_organizer.send(sender=self.request.organizer, request=self.request,
                                             organizer=self.request.organizer):
            ctx['nav_organizer'] += retv
        ctx['nav_organizer'].sort(key=lambda n: n['label'])
        return ctx

    def get_object(self, queryset=None) -> Organizer:
        return self.request.organizer


class OrganizerList(PaginationMixin, ListView):
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
        return ctx

    @cached_property
    def filter_form(self):
        return OrganizerFilterForm(data=self.request.GET, request=self.request)


class BillingSettings(FormView, OrganizerPermissionRequiredMixin):
    model = OrganizerBillingModel
    form_class = BillingSettingsForm
    template_name = "pretixcontrol/organizers/billing.html"
    permission = "can_change_organizer_settings"

    def get_success_url(self):
        return reverse(
            "control:organizer.settings.billing",
            kwargs={
                "organizer": self.request.organizer.slug,
            },
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organizer"] = self.request.organizer
        return kwargs

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        form = self.get_form()

        if form.is_valid():
            try:
                form.save()
                messages.success(self.request, _("Your changes have been saved."))
                return redirect(self.get_success_url())
            except Exception as e:
                logger.error("Error saving billing settings: %s", str(e))
                messages.error(
                    self.request,
                    _("We could not save your changes. See below for details."),
                )
        else:
            messages.error(
                self.request,
                _("We could not save your changes. See below for details."),
            )

        return self.form_invalid(form)
