import sys
from datetime import UTC
from zoneinfo import ZoneInfo
import dateutil.parser

from cron_descriptor import Options, get_description
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DeleteView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)
from django_celery_beat.models import PeriodicTask, PeriodicTasks
from django_context_decorator import context

from django.utils.timezone import make_aware, is_aware
from django.utils.functional import cached_property
from redis.exceptions import RedisError

from eventyay.celery_app import app
from eventyay.control.forms.filter import AttendeeFilterForm
from eventyay.control.forms.admin.admin import UpdateSettingsForm

from eventyay.base.models.checkin import Checkin
from eventyay.base.models.orders import OrderPosition
from eventyay.base.models.organizer import Organizer
from eventyay.base.models.settings import GlobalSettings
from eventyay.base.models.submission import Submission
from eventyay.base.models.vouchers import InvoiceVoucher
from eventyay.base.services.update_check import check_result_table, update_check
from eventyay.common.text.phrases import phrases
from eventyay.control.forms.admin.vouchers import InvoiceVoucherForm
from eventyay.control.forms.filter import OrganizerFilterForm, SubmissionFilterForm, TaskFilterForm
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.control.views import PaginationMixin
from eventyay.control.views.main import EventList


import logging
logger = logging.getLogger(__name__)

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


class AttendeeListView(ListView):
    template_name = 'pretixcontrol/admin/attendees/index.html'
    context_object_name = 'attendees'
    paginate_by = 25

    @cached_property
    def filter_form(self):
        return AttendeeFilterForm(data=self.request.GET)

    def get_queryset(self):
        qs = (
            OrderPosition.objects.select_related('order', 'product', 'order__event', 'order__event__organizer')
            .prefetch_related('checkins')
            .filter(order__status='p')
        )

        if not self.request.user.has_active_staff_session(self.request.session.session_key):
            allowed_organizers = self.request.user.teams.values_list('organizer', flat=True)
            qs = qs.filter(order__event__organizer_id__in=allowed_organizers)

        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)

        ordering = self.request.GET.get('ordering')

        if not ordering:
            qs = qs.order_by('-order__event__date_from', 'order__event__name')
        else:
            ordering_map = {
                'name': 'attendee_name_cached',
                '-name': '-attendee_name_cached',
                'email': 'attendee_email',
                '-email': '-attendee_email',
                'event': 'order__event__name',
                '-event': '-order__event__name',
                'order_code': 'order__code',
                '-order_code': '-order__code',
                'product': 'product__name',
                '-product': '-product__name',
            }
            if ordering in ordering_map:
                qs = qs.order_by(ordering_map[ordering])

        attendees = []

        for pos in qs:
            name = pos.attendee_name_cached or ''
            email = pos.attendee_email or pos.order.email
            event = pos.order.event.name
            order_code = pos.order.code
            product = str(pos.product.name)

            event_slug = pos.order.event.slug
            organizer_slug = pos.order.event.organizer.slug

            testmode = pos.order.testmode

            checkins = pos.checkins.all()
            entry_checkin = checkins.filter(type=Checkin.TYPE_ENTRY).order_by('-datetime').first()
            exit_checkin = checkins.filter(type=Checkin.TYPE_EXIT).order_by('-datetime').first()

            def parse_datetime(dt):
                if not dt:
                    return None
                if isinstance(dt, str):
                    return make_aware(dateutil.parser.parse(dt), UTC)
                elif not is_aware(dt):
                    return make_aware(dt, UTC)
                else:
                    return dt

            entry_time = parse_datetime(entry_checkin.datetime if entry_checkin else None)
            exit_time = parse_datetime(exit_checkin.datetime if exit_checkin else None)

            if not entry_time and not exit_time:
                check_in_status = 'Not checked in'
            elif entry_time and not exit_time:
                check_in_status = 'Checked in'
            elif not entry_time and exit_time:
                check_in_status = 'Checked out (no entry record)'
            elif exit_time < entry_time:
                check_in_status = 'Invalid check-in data (exit before entry)'
            elif exit_time == entry_time:
                check_in_status = 'Checked in and out at same time'
            else:
                check_in_status = 'Checked in but left'

            attendees.append(
                {
                    'name': name,
                    'email': email,
                    'event': event,
                    'event_slug': event_slug,
                    'organizer_slug': organizer_slug,
                    'order_code': order_code,
                    'product': product,
                    'check_in_status': check_in_status,
                    'testmode': testmode,
                }
            )

        if ordering in ('check_in_status', '-check_in_status'):
            reverse_sort = ordering.startswith('-')
            attendees.sort(key=lambda x: x['check_in_status'], reverse=reverse_sort)

        return attendees

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        return ctx


class SubmissionListView(ListView):
    template_name = 'pretixcontrol/admin/submissions/index.html'
    context_object_name = 'submissions'
    paginate_by = 25

    @cached_property
    def filter_form(self):
        return SubmissionFilterForm(data=self.request.GET)

    def get_queryset(self):
        from django_scopes import scopes_disabled
        with scopes_disabled():
            qs = (
                Submission.objects.select_related('event', 'submission_type')
                .prefetch_related('speakers')
            )

            # Restrict for non-staff users
            if not self.request.user.has_active_staff_session(self.request.session.session_key):
                allowed_organizers = self.request.user.teams.values_list('organizer', flat=True)
                qs = qs.filter(event__organizer_id__in=allowed_organizers)

            # Apply filters
            if self.filter_form.is_valid():
                qs = self.filter_form.filter_qs(qs)

            # Ordering logic
            ordering = self.request.GET.get('ordering')
            ordering_map = {
                'title': 'title',
                '-title': '-title',
                'event': 'event__name',
                '-event': '-event__name',
                'speakers': 'speakers__fullname',
                '-speakers': '-speakers__fullname',
                'state': 'state',
                '-state': '-state',
                'session_type': 'submission_type__name',
                '-session_type': '-submission_type__name',
            }

            if ordering in ordering_map:
                qs = qs.order_by(ordering_map[ordering])
            else:
                qs = qs.order_by('-event__date_from', 'title')

            # Build display list
            submissions = []
            for s in qs:
                speakers = ', '.join(sp.get_display_name() for sp in s.speakers.all())
                submissions.append({
                    'title': s.title,
                    'speakers': speakers,
                    'event': s.event.name,
                    'session_type': s.submission_type.name if s.submission_type else '',
                    'proposal_state': s.state,
                    'event_slug': s.event.slug,
                    'organizer_slug': s.event.organizer.slug,
                    'code': s.code,
                    'track': s.track.name if s.track else '',
                    'tags': ', '.join(t.tag for t in s.tags.all()) if s.tags else '',
                })

        return submissions
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        return ctx


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

            return HttpResponseRedirect(reverse('eventyay_admin:admin.task_management'))


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
        return reverse('eventyay_admin:admin.vouchers')

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
        return reverse('eventyay_admin:admin.vouchers')


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
        return reverse('eventyay_admin:admin.vouchers')
