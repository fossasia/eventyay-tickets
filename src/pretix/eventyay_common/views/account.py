import base64
from datetime import datetime, UTC
from logging import getLogger
from collections import defaultdict
from urllib.parse import quote, urlencode
from typing import Any, cast

from django.urls import reverse
from django.shortcuts import redirect, get_object_or_404
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.forms import BaseForm
from django.views.generic import UpdateView, TemplateView, FormView
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils.functional import cached_property
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.contrib.auth.mixins import LoginRequiredMixin
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from pretix.common.consts import KEY_LAST_FORCE_LOGIN
from pretix.base.models import User, Event, NotificationSetting, WebAuthnDevice, U2FDevice
from pretix.base.notifications import get_all_notification_types
from pretix.base.forms.user import UserSettingsForm, User2FADeviceAddForm
from ..navigation import get_account_navigation


REAL_DEVICE_TYPES = (TOTPDevice, WebAuthnDevice, U2FDevice)
logger = getLogger(__name__)


class RecentAuthenticationRequiredMixin:
    max_time = 3600

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(reverse('control:user.login'))
        user = cast(User, request.user)
        last_login_secs = cast(float | None, request.session.get(KEY_LAST_FORCE_LOGIN))
        if not last_login_secs:
            logger.warning('Something wrong with our authentication system. User %s has no last_login set.', user)
            messages.error(request, _('Something went wrong, you cannot access this page now.'))
            return redirect('/')
        last_login = datetime.fromtimestamp(last_login_secs, tz=UTC)
        logger.info('User %s last login: %s', user, last_login)
        delta = timezone.now() - last_login
        if delta.total_seconds() > self.max_time:
            auth_url = reverse('control:user.reauth')
            auth_url = '{}?{}'.format(auth_url, urlencode({'next': request.path}))
            return redirect(auth_url)
        return super().dispatch(request, *args, **kwargs)


class AccountMenuMixIn:
    def get_context_data(self, **kwargs) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['nav_items'] = get_account_navigation(self.request)
        return ctx


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
                if 'new_pw' == k:
                    data['new_pw'] = True
                else:
                    data[k] = form.cleaned_data[k]

        msgs = []

        if 'new_pw' in form.changed_data:
            msgs.append(_('Your password has been changed.'))

        if 'email' in form.changed_data:
            msgs.append(_('Your email address has been changed to {email}.').format(email=form.cleaned_data['email']))

        if msgs:
            self.request.user.send_security_notice(msgs, email=form.cleaned_data['email'])
            if self._old_email != form.cleaned_data['email']:
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
                return self.request.user.get_events_with_any_permission().select_related(
                    'organizer'
                ).get(pk=self.request.GET.get('event'))
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
        if "notifications_send" in request.POST:
            request.user.notifications_send = request.POST.get("notifications_send", "") == "on"
            request.user.save()

            messages.success(request, _('Your notification settings have been saved.'))
            if request.user.notifications_send:
                self.request.user.log_action('pretix.user.settings.notifications.disabled', user=self.request.user)
            else:
                self.request.user.log_action('pretix.user.settings.notifications.enabled', user=self.request.user)
            return redirect(
                reverse('eventyay_common:account.notifications') +
                ('?event={}'.format(self.event.pk) if self.event else '')
            )
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
                            event=self.event, action_type=at, method=method, enabled=(val == 'on'),
                        )

                    # False → True
                    if old_enabled.get(at) is False and val == 'on':
                        self.request.user.notification_settings.filter(
                            event=self.event, action_type=at, method=method
                        ).update(enabled=True)

            messages.success(request, _('Your notification settings have been saved.'))
            self.request.user.log_action('pretix.user.settings.notifications.changed', user=self.request.user)
            return redirect(
                reverse('eventyay_common:account.notifications') +
                ('?event={}'.format(self.event.pk) if self.event else '')
            )

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


class TwoFactorAuthSettingsView(RecentAuthenticationRequiredMixin, AccountMenuMixIn, TemplateView):
    template_name = 'eventyay_common/account/2fa-main-settings.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()

        try:
            ctx['static_tokens'] = StaticDevice.objects.get(user=self.request.user, name='emergency').token_set.all()
        except StaticDevice.MultipleObjectsReturned:
            ctx['static_tokens'] = StaticDevice.objects.filter(
                user=self.request.user, name='emergency'
            ).first().token_set.all()
        except StaticDevice.DoesNotExist:
            d = StaticDevice.objects.create(user=self.request.user, name='emergency')
            for i in range(10):
                d.token_set.create(token=get_random_string(length=12, allowed_chars='1234567890'))
            ctx['static_tokens'] = d.token_set.all()

        ctx['devices'] = []
        for dt in REAL_DEVICE_TYPES:
            objs = list(dt.objects.filter(user=self.request.user, confirmed=True))
            for obj in objs:
                if dt == TOTPDevice:
                    obj.devicetype = 'totp'
                elif dt == U2FDevice:
                    obj.devicetype = 'u2f'
                elif dt == WebAuthnDevice:
                    obj.devicetype = 'webauthn'
            ctx['devices'] += objs

        return ctx


class TwoFactorAuthEnableView(RecentAuthenticationRequiredMixin, AccountMenuMixIn, TemplateView):
    template_name = 'eventyay_common/account/2fa-enable.html'

    def dispatch(self, request, *args, **kwargs):
        if not any(dt.objects.filter(user=self.request.user, confirmed=True) for dt in REAL_DEVICE_TYPES):
            messages.error(request, _('Please configure at least one device before enabling two-factor '
                                      'authentication.'))
            return redirect(reverse('eventyay_common:account.2fa'))
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.request.user.require_2fa = True
        self.request.user.save()
        self.request.user.log_action('pretix.user.settings.2fa.enabled', user=self.request.user)
        messages.success(request, _('Two-factor authentication is now enabled for your account.'))
        self.request.user.send_security_notice([
            _('Two-factor authentication has been enabled.')
        ])
        self.request.user.update_session_token()
        update_session_auth_hash(self.request, self.request.user)
        return redirect(reverse('eventyay_common:account.2fa'))


class TwoFactorAuthDisableView(RecentAuthenticationRequiredMixin, AccountMenuMixIn, TemplateView):
    template_name = 'eventyay_common/account/2fa-disable.html'

    def post(self, request, *args, **kwargs):
        self.request.user.require_2fa = False
        self.request.user.save()
        self.request.user.log_action('pretix.user.settings.2fa.disabled', user=self.request.user)
        messages.success(request, _('Two-factor authentication is now disabled for your account.'))
        self.request.user.send_security_notice([
            _('Two-factor authentication has been disabled.')
        ])
        self.request.user.update_session_token()
        update_session_auth_hash(self.request, self.request.user)
        return redirect(reverse('eventyay_common:account.2fa'))


class TwoFactorAuthDeviceAddView(RecentAuthenticationRequiredMixin, AccountMenuMixIn, FormView):
    form_class = User2FADeviceAddForm
    template_name = 'eventyay_common/account/2fa-add.html'

    def form_valid(self, form: BaseForm) -> HttpResponse:
        if form.cleaned_data['devicetype'] == 'totp':
            dev = TOTPDevice.objects.create(user=self.request.user, confirmed=False, name=form.cleaned_data['name'])
        elif form.cleaned_data['devicetype'] == 'webauthn':
            if not self.request.is_secure():
                messages.error(self.request,
                               _('Security devices are only available if pretix is served via HTTPS.'))
                return self.get(self.request, self.args, self.kwargs)
            dev = WebAuthnDevice.objects.create(user=self.request.user, confirmed=False, name=form.cleaned_data['name'])
        next_url_name = 'eventyay_common:account.2fa.confirm.{}'.format(form.cleaned_data['devicetype'])
        return redirect(reverse(next_url_name, kwargs={
            'device_id': dev.pk
        }))

    def form_invalid(self, form: BaseForm) -> HttpResponse:
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)


class TwoFactorAuthDeviceConfirmTOTPView(RecentAuthenticationRequiredMixin, AccountMenuMixIn, TemplateView):
    template_name = 'eventyay_common/account/2fa-confirm-totp.html'

    @cached_property
    def device(self) -> TOTPDevice:
        return get_object_or_404(TOTPDevice, user=self.request.user, pk=self.kwargs['device_id'], confirmed=False)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()

        ctx['secret'] = base64.b32encode(self.device.bin_key).decode('utf-8')
        ctx['secretGrouped'] = "  ".join([ctx['secret'].lower()[(i * 4): (i + 1) * 4] for i in range(len(ctx['secret']) // 4)])
        label = f"{settings.INSTANCE_NAME}: {self.request.user.email}"
        ctx['qrdata'] = 'otpauth://totp/{}?{}'.format(
            quote(label),
            urlencode({
                'issuer': settings.INSTANCE_NAME,
                'secret': ctx['secret'],
                'digits': self.device.digits
            })
        )
        ctx['device'] = self.device
        return ctx

    def post(self, request: HttpRequest, *args, **kwargs):
        token = request.POST.get('token', '')
        activate = request.POST.get('activate', '')
        user = cast(User, request.user)
        if self.device.verify_token(token):
            self.device.confirmed = True
            self.device.save()
            user.log_action('pretix.user.settings.2fa.device.added', user=user, data={
                'id': self.device.pk,
                'name': self.device.name,
                'devicetype': 'totp'
            })
            notices = [
                _('A new two-factor authentication device has been added to your account.')
            ]
            if activate == 'on' and not user.require_2fa:
                user.require_2fa = True
                user.save()
                user.log_action('pretix.user.settings.2fa.enabled', user=user)
                notices.append(
                    _('Two-factor authentication has been enabled.')
                )
            user.send_security_notice(notices)
            user.update_session_token()
            update_session_auth_hash(self.request, user)

            note = ''
            if not user.require_2fa:
                note = ' ' + str(_('Please note that you still need to enable two-factor authentication for your '
                                   'account using the buttons below to make a second factor required for logging '
                                   'into your account.'))
            messages.success(request, str(_('The device has been verified and can now be used.')) + note)
            return redirect(reverse('eventyay_common:account.2fa'))
        else:
            messages.error(request, _('The code you entered was not valid. If this problem persists, please check '
                                      'that the date and time of your phone are configured correctly.'))
            return redirect(reverse('eventyay_common:account.2fa.confirm.totp', kwargs={
                'device_id': self.device.pk
            }))


class TwoFactorAuthDeviceDeleteView(RecentAuthenticationRequiredMixin, AccountMenuMixIn, TemplateView):
    template_name = 'eventyay_common/account/2fa-delete.html'

    @cached_property
    def device(self):
        if self.kwargs['devicetype'] == 'totp':
            return get_object_or_404(TOTPDevice, user=self.request.user, pk=self.kwargs['device'], confirmed=True)
        elif self.kwargs['devicetype'] == 'webauthn':
            return get_object_or_404(WebAuthnDevice, user=self.request.user, pk=self.kwargs['device'], confirmed=True)
        elif self.kwargs['devicetype'] == 'u2f':
            return get_object_or_404(U2FDevice, user=self.request.user, pk=self.kwargs['device'], confirmed=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['device'] = self.device
        return ctx

    def post(self, request, *args, **kwargs):
        self.request.user.log_action('pretix.user.settings.2fa.device.deleted', user=self.request.user, data={
            'id': self.device.pk,
            'name': self.device.name,
            'devicetype': self.kwargs['devicetype']
        })
        self.device.delete()
        msgs = [
            _('A two-factor authentication device has been removed from your account.')
        ]
        if not any(dt.objects.filter(user=self.request.user, confirmed=True) for dt in REAL_DEVICE_TYPES):
            self.request.user.require_2fa = False
            self.request.user.save()
            self.request.user.log_action('pretix.user.settings.2fa.disabled', user=self.request.user)
            msgs.append(_('Two-factor authentication has been disabled.'))

        self.request.user.send_security_notice(msgs)
        self.request.user.update_session_token()
        update_session_auth_hash(self.request, self.request.user)
        messages.success(request, _('The device has been removed.'))
        return redirect(reverse('eventay_common:account.2fa'))


# This view is just a placeholder for the URL patterns that we haven't implemented views for yet.
class DummyView(TemplateView):
    template_name = 'eventyay_common/base.html'
