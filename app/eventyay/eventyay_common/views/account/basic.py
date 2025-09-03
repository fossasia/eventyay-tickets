from logging import getLogger
from collections import defaultdict

from django.urls import reverse
from django.shortcuts import redirect, get_object_or_404
from django.http import HttpRequest, HttpResponse
from django.views.generic import UpdateView, TemplateView, ListView
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils.functional import cached_property
from django.contrib.auth.mixins import LoginRequiredMixin
from django_scopes import scopes_disabled

from eventyay.base.models import User, Event, NotificationSetting, LogEntry
from eventyay.base.notifications import get_all_notification_types
from eventyay.base.forms.user import UserSettingsForm
from ...navigation import get_account_navigation
from .common import AccountMenuMixIn


logger = getLogger(__name__)


# Copied from src/pretix/control/views/user.py and modified.
class GeneralSettingsView(LoginRequiredMixin, AccountMenuMixIn, UpdateView):
    model = User
    form_class = UserSettingsForm
    template_name = 'eventyay_common/account/general-settings.html'

    def get_object(self, queryset=None):
        self._old_email = self.request.user.email
        return self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved. See below for details.'))
        return super().form_invalid(form)

    def form_valid(self, form):
        messages.success(self.request, _('Your changes have been saved.'))

        data = {}
        for k in form.changed_data:
            if k not in ('old_pw', 'new_pw_repeat'):
                if k == 'new_pw':
                    data['new_pw'] = True
                else:
                    data[k] = form.cleaned_data[k]

        msgs = []

        if 'new_pw' in form.changed_data:
            msgs.append(_('Your password has been changed.'))

        email_addr = form.cleaned_data['email']
        if 'email' in form.changed_data:
            msgs.append(_('Your email address has been changed to {email}.').format(email=email_addr))

        if msgs:
            self.request.user.send_security_notice(msgs, email=email_addr)
            if self._old_email != email_addr:
                self.request.user.send_security_notice(msgs, email=self._old_email)

        sup = super().form_valid(form)
        self.request.user.log_action('pretix.user.settings.changed', user=self.request.user, data=data)

        update_session_auth_hash(self.request, self.request.user)
        return sup

    def get_success_url(self):
        return reverse('eventyay_common:account')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['nav_items'] = get_account_navigation(self.request)
        return ctx


class NotificationSettingsView(LoginRequiredMixin, AccountMenuMixIn, TemplateView):
    template_name = 'eventyay_common/account/notification-settings.html'

    @cached_property
    def event(self):
        if self.request.GET.get('event'):
            try:
                return (
                    self.request.user.get_events_with_any_permission()
                    .select_related('organizer')
                    .get(pk=self.request.GET.get('event'))
                )
            except Event.DoesNotExist:
                return None
        return None

    @cached_property
    def types(self):
        return get_all_notification_types(self.event)

    @cached_property
    def currently_set(self):
        set_per_method = defaultdict(dict)
        for n in self.request.user.notification_settings.filter(event=self.event):
            set_per_method[n.method][n.action_type] = n.enabled
        return set_per_method

    @cached_property
    def global_set(self):
        set_per_method = defaultdict(dict)
        for n in self.request.user.notification_settings.filter(event__isnull=True):
            set_per_method[n.method][n.action_type] = n.enabled
        return set_per_method

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if 'notifications_send' in request.POST:
            request.user.notifications_send = request.POST.get('notifications_send', '') == 'on'
            request.user.save()

            messages.success(request, _('Your notification settings have been saved.'))
            if request.user.notifications_send:
                self.request.user.log_action('pretix.user.settings.notifications.disabled', user=self.request.user)
            else:
                self.request.user.log_action('pretix.user.settings.notifications.enabled', user=self.request.user)
            dest = reverse('eventyay_common:account.notifications')
            if self.event:
                dest += '?event={}'.format(self.event.pk)
            return redirect(dest)
        else:
            for method, __ in NotificationSetting.CHANNELS:
                old_enabled = self.currently_set[method]

                for at in self.types.keys():
                    val = request.POST.get('{}:{}'.format(method, at))

                    # True → False
                    if old_enabled.get(at) is True and val == 'off':
                        self.request.user.notification_settings.filter(
                            event=self.event, action_type=at, method=method
                        ).update(enabled=False)

                    # True/False → None
                    if old_enabled.get(at) is not None and val == 'global':
                        self.request.user.notification_settings.filter(
                            event=self.event, action_type=at, method=method
                        ).delete()

                    # None → True/False
                    if old_enabled.get(at) is None and val in ('on', 'off'):
                        self.request.user.notification_settings.create(
                            event=self.event,
                            action_type=at,
                            method=method,
                            enabled=(val == 'on'),
                        )

                    # False → True
                    if old_enabled.get(at) is False and val == 'on':
                        self.request.user.notification_settings.filter(
                            event=self.event, action_type=at, method=method
                        ).update(enabled=True)

            messages.success(request, _('Your notification settings have been saved.'))
            self.request.user.log_action('pretix.user.settings.notifications.changed', user=self.request.user)
            dest = reverse('eventyay_common:account.notifications')
            if self.event:
                dest += '?event={}'.format(self.event.pk)
            return redirect(dest)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['events'] = self.request.user.get_events_with_any_permission().order_by('-date_from')
        ctx['types'] = [
            (
                tv,
                {k: a.get(t) for k, a in self.currently_set.items()},
                {k: a.get(t) for k, a in self.global_set.items()},
            )
            for t, tv in self.types.items()
        ]
        ctx['event'] = self.event
        if self.event:
            ctx['permset'] = self.request.user.get_event_permission_set(self.event.organizer, self.event)
        return ctx


class NotificationFlipOffView(TemplateView):
    template_name = 'eventyay_common/account/notification-flip-off.html'

    @scopes_disabled()
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        user = get_object_or_404(User, notifications_token=kwargs.get('token'), pk=kwargs.get('id'))
        user.notifications_send = False
        user.save()
        messages.success(request, _('Your notifications have been disabled.'))
        dest = (
            reverse('eventyay_common:account.notifications')
            if request.user.is_authenticated
            else reverse('control:auth.login')
        )
        return redirect(dest)


class HistoryView(AccountMenuMixIn, ListView):
    template_name = 'eventyay_common/account/history.html'
    model = LogEntry
    context_object_name = 'logs'
    paginate_by = 20

    def get_queryset(self):
        qs = (
            LogEntry.objects.filter(
                content_type=ContentType.objects.get_for_model(User), object_id=self.request.user.pk
            )
            .select_related('user', 'content_type', 'api_token', 'oauth_application', 'device')
            .order_by('-datetime')
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()

        class FakeClass:
            def top_logentries(self):
                return ctx['logs']

        ctx['fakeobj'] = FakeClass()
        return ctx


# This view is just a placeholder for the URL patterns that we haven't implemented views for yet.
class DummyView(TemplateView):
    template_name = 'eventyay_common/base.html'
