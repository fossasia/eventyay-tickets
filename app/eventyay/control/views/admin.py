from zoneinfo import ZoneInfo

from cron_descriptor import Options, get_description
from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)
from django_celery_beat.models import PeriodicTask, PeriodicTasks

from eventyay.base.models import Organizer
from eventyay.base.models.vouchers import InvoiceVoucher
from eventyay.control.forms.admin.vouchers import InvoiceVoucherForm
from eventyay.control.forms.filter import OrganizerFilterForm, TaskFilterForm
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.control.views import PaginationMixin
from eventyay.control.views.main import EventList


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
    """Inherit from EventList to add a custom template for the admin event list."""

    template_name = 'pretixcontrol/admin/events/index.html'


class TaskList(PaginationMixin, ListView):
    template_name = 'pretixcontrol/admin/task_management/task_management.html'
    context_object_name = 'tasks'
    model = PeriodicTask

    @cached_property
    def filter_form(self):
        return TaskFilterForm(data=self.request.GET)

    def get_queryset(self):
        queryset = super().get_queryset().exclude(name='celery.backend_cleanup').select_related('crontab')

        if self.filter_form.is_valid():
            queryset = self.filter_form.filter_qs(queryset)

        return queryset

    def process_task_data(self, task):
        if task.last_run_at is None:
            task.formatted_last_run_at = '-'
        else:
            local_timezone = ZoneInfo(settings.TIME_ZONE)
            task.formatted_last_run_at = date_format(
                task.last_run_at.astimezone(local_timezone), format='M. d, Y, g:i a'
            )

        task.name = task.name.replace('_', ' ').capitalize()

        options = Options()
        options.locale_code = settings.LANGUAGE_CODE
        options.verbose = True
        schedule = task.crontab
        cron_expression = (
            f'{schedule.minute} {schedule.hour} {schedule.day_of_month} {schedule.month_of_year} {schedule.day_of_week}'
        )
        task.run_at = get_description(cron_expression, options)

        return task

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['tasks'] = [self.process_task_data(task) for task in context['tasks']]

        context['filter_form'] = self.filter_form
        return context

    def post(self, request, *args, **kwargs):
        task_id = request.POST.get('task_id')
        current_enabled = request.POST.get('enabled') == 'true'

        if task_id:
            task = get_object_or_404(PeriodicTask, id=task_id)
            new_status = not current_enabled

            PeriodicTask.objects.filter(id=task_id).update(enabled=new_status)
            PeriodicTasks.changed(task)

            status_text = 'enabled' if new_status else 'disabled'
            messages.success(
                self.request,
                f'The task {task.name} has been successfully {status_text}.',
            )

            return HttpResponseRedirect(reverse('control:admin.task_management'))


class VoucherList(PaginationMixin, AdministratorPermissionRequiredMixin, ListView):
    model = InvoiceVoucher
    context_object_name = 'vouchers'
    template_name = 'pretixcontrol/admin/vouchers/index.html'

    def get_queryset(self):
        qs = InvoiceVoucher.objects.all()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class VoucherCreate(AdministratorPermissionRequiredMixin, CreateView):
    model = InvoiceVoucher
    template_name = 'pretixcontrol/admin/vouchers/detail.html'
    context_object_name = 'voucher'

    def get_form_class(self):
        form_class = InvoiceVoucherForm
        return form_class

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['currency'] = settings.DEFAULT_CURRENCY
        return ctx

    def get_success_url(self) -> str:
        return reverse('control:admin.vouchers')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs

    def form_valid(self, form):
        req = super().form_valid(form)
        return req

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class VoucherUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    model = InvoiceVoucher
    template_name = 'pretixcontrol/admin/vouchers/detail.html'
    context_object_name = 'voucher'

    def get_form_class(self):
        form_class = InvoiceVoucherForm
        return form_class

    def get_object(self, queryset=None) -> InvoiceVoucherForm:
        try:
            return InvoiceVoucher.objects.get(id=self.kwargs['voucher'])
        except InvoiceVoucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['currency'] = settings.DEFAULT_CURRENCY
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse('control:admin.vouchers')


class VoucherDelete(AdministratorPermissionRequiredMixin, DeleteView):
    model = InvoiceVoucher
    template_name = 'pretixcontrol/admin/vouchers/delete.html'
    context_object_name = 'invoice_voucher'

    def get_object(self, queryset=None) -> InvoiceVoucher:
        try:
            return InvoiceVoucher.objects.get(id=self.kwargs['voucher'])
        except InvoiceVoucher.DoesNotExist:
            raise Http404(_('The requested voucher does not exist.'))

    def get(self, request, *args, **kwargs):
        if self.get_object().redeemed > 0:
            messages.error(
                request,
                _('A voucher can not be deleted if it already has been redeemed.'),
            )
            return HttpResponseRedirect(self.get_success_url())
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = self.get_object()
        success_url = self.get_success_url()

        if self.object.redeemed > 0:
            messages.error(
                self.request,
                _('A voucher can not be deleted if it already has been redeemed.'),
            )
        else:
            self.object.delete()
            messages.success(self.request, _('The selected voucher has been deleted.'))
        return HttpResponseRedirect(success_url)

    def get_success_url(self) -> str:
        return reverse('control:admin.vouchers')
