from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, TemplateView
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from pretix.base.models import Organizer
from pretix.control.forms.filter import OrganizerFilterForm, TaskFilterForm
from pretix.control.permissions import AdministratorPermissionRequiredMixin
from pretix.control.views import PaginationMixin
from pretix.control.views.main import EventList


class AdminDashboard(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class OrganizerList(PaginationMixin, ListView):
    model = Organizer
    context_object_name = 'organizers'
    template_name = 'pretixcontrol/admin/organizers.html'

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


class AdminEventList(EventList):
    """ Inherit from EventList to add a custom template for the admin event list. """
    template_name = 'pretixcontrol/admin/events/index.html'


class TaskList(PaginationMixin, ListView):
    template_name = 'pretixcontrol/admin/task_management/task_management.html'
    context_object_name = 'tasks'
    model = PeriodicTask

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.filter_form.is_valid():
            queryset = self.filter_form.filter_qs(queryset)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        return context

    def post(self, request, *args, **kwargs):
        task_id = request.POST.get('task_id')
        current_enabled = request.POST.get('enabled') == 'true'

        if task_id:
            task = get_object_or_404(PeriodicTask, id=task_id)
            task.enabled = not current_enabled
            task.save()
            messages.success(self.request, _('The task {} has been successfully {}.'.format(task.name,
                'enabled' if task.enabled else 'disabled'
            )))

        return HttpResponseRedirect(reverse('control:admin.task_management'))

    @cached_property
    def filter_form(self):
        return TaskFilterForm(data=self.request.GET)
