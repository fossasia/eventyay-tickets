import logging
from urllib.parse import urljoin

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView

from eventyay.base.models import Organizer, Team
from eventyay.control.forms.filter import OrganizerFilterForm
from eventyay.control.views import CreateView, PaginationMixin, UpdateView

from ...control.forms.organizer_forms import OrganizerForm, OrganizerUpdateForm
from ...control.permissions import OrganizerPermissionRequiredMixin

logger = logging.getLogger(__name__)


class OrganizerList(PaginationMixin, ListView):
    model = Organizer
    context_object_name = 'organizers'
    template_name = 'eventyay_common/organizers/index.html'

    def get_queryset(self):
        qs = Organizer.objects.all()
        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)
        if not self.request.user.has_active_staff_session(self.request.session.session_key):
            qs = qs.filter(pk__in=self.request.user.teams.values_list('organizer', flat=True))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        return ctx

    @cached_property
    def filter_form(self):
        return OrganizerFilterForm(data=self.request.GET, request=self.request)


class OrganizerCreate(CreateView):
    model = Organizer
    form_class = OrganizerForm
    template_name = 'eventyay_common/organizers/create.html'
    context_object_name = 'organizer'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_active_staff_session(self.request.session.session_key):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, _('New organizer is created.'))
        response = super().form_valid(form)
        team = Team.objects.create(
            organizer=form.instance,
            name=_('Administrators'),
            all_events=True,
            can_create_events=True,
            can_change_teams=True,
            can_manage_gift_cards=True,
            can_change_organizer_settings=True,
            can_change_event_settings=True,
            can_change_items=True,
            can_view_orders=True,
            can_change_orders=True,
            can_view_vouchers=True,
            can_change_vouchers=True,
        )
        # Trigger webhook in talk to create organiser in talk component
        team.members.add(self.request.user)
        return response

    def get_success_url(self) -> str:
        return reverse('eventyay_common:organizers')

class OrganizerUpdate(UpdateView, OrganizerPermissionRequiredMixin):
    model = Organizer
    form_class = OrganizerUpdateForm
    template_name = 'eventyay_common/organizers/edit.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'organizer'

    @cached_property
    def object(self) -> Organizer:
        return self.request.organizer

    def get_object(self, queryset=None) -> Organizer:
        return self.object

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.object

        # Add Teams section only if user has team permissions
        user = self.request.user
        if user.has_organizer_permission(org, 'can_change_teams', request=self.request):
            ctx['teams'] = (
                org.teams.annotate(
                    memcount=Count('members', distinct=True),
                    eventcount=Count('limit_events', distinct=True),
                    invcount=Count('invites', distinct=True),
                )
                .all()
                .order_by('name')
            )
            ctx['can_manage_teams'] = True
        else:
            ctx['teams'] = []
            ctx['can_manage_teams'] = False

        return ctx
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        can_edit_general_info = self.request.user.has_organizer_permission(
            self.request.organizer,
            'can_change_organizer_settings',
            request=self.request
        )
        
        if not can_edit_general_info:
            form.fields['name'].disabled = True
            form.fields['slug'].disabled = True

        return form

    @transaction.atomic
    def form_valid(self, form):
        can_edit_general_info = self.request.user.has_organizer_permission(
            self.request.organizer,
            'can_change_organizer_settings',
            request=self.request
        )

        if not can_edit_general_info:
            form.cleaned_data['name'] = self.object.name
            form.cleaned_data['slug'] = self.object.slug

        messages.success(self.request, _('Your changes have been saved.'))
        response = super().form_valid(form)
        return response

    def get_success_url(self) -> str:
        return reverse('eventyay_common:organizers')
