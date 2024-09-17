from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch, Min, Max, F
from django.db.models.functions import Greatest, Coalesce
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _, gettext
from django.views.generic import ListView
from i18nfield.strings import LazyI18nString

from pretix.base.forms import SafeSessionWizardView
from pretix.base.i18n import language
from pretix.base.models import Event, EventMetaValue, Quota, Organizer, Team
from pretix.base.services.quotas import QuotaAvailability
from pretix.control.forms.event import EventWizardFoundationForm, EventWizardBasicsForm
from pretix.control.forms.filter import EventFilterForm
from pretix.control.views import PaginationMixin


class EventList(PaginationMixin, ListView):
    model = Event
    context_object_name = 'events'
    template_name = 'eventyay_common/events/index.html'

    def get_queryset(self):
        query_set = self.request.user.get_events_with_any_permission(self.request).prefetch_related(
            'organizer', '_settings_objects', 'organizer___settings_objects', 'organizer__meta_properties',
            Prefetch(
                'meta_values',
                EventMetaValue.objects.select_related('property'),
                to_attr='meta_values_cached'
            )
        ).order_by('-date_from')

        query_set = query_set.annotate(
            min_from=Min('subevents__date_from'),
            max_from=Max('subevents__date_from'),
            max_to=Max('subevents__date_to'),
            max_fromto=Greatest(Max('subevents__date_to'), Max('subevents__date_from'))
        ).annotate(
            order_from=Coalesce('min_from', 'date_from'),
            order_to=Coalesce('max_fromto', 'max_to', 'max_from', 'date_to', 'date_from'),
        )

        query_set = query_set.prefetch_related(
            Prefetch('quotas',
                     queryset=Quota.objects.filter(subevent__isnull=True).annotate(s=Coalesce(F('size'), 0)).order_by(
                         '-s'),
                     to_attr='first_quotas')
        )

        if self.filter_form.is_valid():
            query_set = self.filter_form.filter_qs(query_set)
        return query_set

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form

        quotas = []
        for s in ctx['events']:
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
                    round(q.cached_availability_paid_orders / q.size * 100) if q.size > 0 else 100
                )
        return ctx

    @cached_property
    def filter_form(self):
        return EventFilterForm(data=self.request.GET, request=self.request)


class EventCreateView(SafeSessionWizardView):
    form_list = [
        ('foundation', EventWizardFoundationForm),
        ('basics', EventWizardBasicsForm),
    ]
    templates = {
        'foundation': 'eventyay_common/events/create_foundation.html',
        'basics': 'eventyay_common/events/create_basics.html',
    }
    condition_dict = {}

    def get_form_initial(self, step):
        initial = super().get_form_initial(step)
        if 'organizer' in self.request.GET:
            if step == 'foundation':
                try:
                    qs = Organizer.objects.all()
                    if not self.request.user.has_active_staff_session(self.request.session.session_key):
                        qs = qs.filter(
                            id__in=self.request.user.teams.filter(can_create_events=True).values_list('organizer',
                                                                                                      flat=True)
                        )
                    initial['organizer'] = qs.get(slug=self.request.GET.get('organizer'))
                except Organizer.DoesNotExist:
                    pass

        return initial

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, form, **kwargs):
        ctx = super().get_context_data(form, **kwargs)
        ctx['has_organizer'] = self.request.user.teams.filter(can_create_events=True).exists()
        if self.steps.current == 'basics':
            ctx['organizer'] = self.get_cleaned_data_for_step('foundation').get('organizer')
        return ctx

    def render(self, form=None, **kwargs):
        if self.steps.current != 'foundation':
            fdata = self.get_cleaned_data_for_step('foundation')
            if fdata is None:
                return self.render_goto_step('foundation')

        return super().render(form, **kwargs)

    def get_form_kwargs(self, step=None):
        kwargs = {
            'user': self.request.user,
            'session': self.request.session,
        }
        if step != 'foundation':
            fdata = self.get_cleaned_data_for_step('foundation')
            if fdata is None:
                fdata = {
                    'organizer': Organizer(slug='_nonexisting'),
                    'has_subevents': False,
                    'locales': ['en']
                }
                # The show must go on, we catch this error in render()
            kwargs.update(fdata)
        return kwargs

    def get_template_names(self):
        return [self.templates[self.steps.current]]

    def done(self, form_list, form_dict, **kwargs):
        foundation_data = self.get_cleaned_data_for_step('foundation')
        basics_data = self.get_cleaned_data_for_step('basics')

        with transaction.atomic(), language(basics_data['locale']):
            event = form_dict['basics'].instance
            event.organizer = foundation_data['organizer']
            event.plugins = settings.PRETIX_PLUGINS_DEFAULT
            event.has_subevents = foundation_data['has_subevents']
            event.testmode = True
            form_dict['basics'].save()

            event.checkin_lists.create(
                name=_('Default'),
                all_products=True
            )
            event.set_defaults()
            event.settings.set('timezone', basics_data['timezone'])
            event.settings.set('locale', basics_data['locale'])
            event.settings.set('locales', foundation_data['locales'])

        return redirect(reverse('eventyay_common:events') + '?congratulations=1')
