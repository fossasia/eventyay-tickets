import base64
import json
from datetime import datetime, UTC
from logging import getLogger
from urllib.parse import quote, urlencode, urlparse
from typing import cast

import webauthn
from django.urls import reverse
from django.shortcuts import redirect, get_object_or_404
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.forms import BaseForm
from django.views.generic import TemplateView, FormView
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.utils.translation import gettext, gettext_lazy as _
from django.utils.functional import cached_property
from django.utils import timezone
from django.utils.crypto import get_random_string
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from webauthn.helpers import generate_challenge, generate_user_handle

from eventyay.common.consts import KEY_LAST_FORCE_LOGIN
from eventyay.base.models import User, WebAuthnDevice, U2FDevice
from eventyay.base.forms.user import User2FADeviceAddForm
from eventyay.helpers.u2f import websafe_encode
from .common import AccountMenuMixIn


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


class TwoFactorAuthPageMixin(RecentAuthenticationRequiredMixin, AccountMenuMixIn):
    pass


class TwoFactorAuthSettingsView(TwoFactorAuthPageMixin, TemplateView):
    template_name = 'eventyay_common/account/2fa-main-settings.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()

        try:
            ctx['static_tokens'] = StaticDevice.objects.get(user=self.request.user, name='emergency').token_set.all()
        except StaticDevice.MultipleObjectsReturned:
            ctx['static_tokens'] = (
                StaticDevice.objects.filter(user=self.request.user, name='emergency').first().token_set.all()
            )
        except StaticDevice.DoesNotExist:
            d = StaticDevice.objects.create(user=self.request.user, name='emergency')
            for _i in range(10):
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


class TwoFactorAuthEnableView(TwoFactorAuthPageMixin, TemplateView):
    template_name = 'eventyay_common/account/2fa-enable.html'

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        if not any(dt.objects.filter(user=self.request.user, confirmed=True) for dt in REAL_DEVICE_TYPES):
            messages.error(
                request, _('Please configure at least one device before enabling two-factor authentication.')
            )
            return redirect(reverse('eventyay_common:account.2fa'))
        return super().dispatch(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args, **kwargs):
        request.user.require_2fa = True
        request.user.save()
        request.user.log_action('pretix.user.settings.2fa.enabled', user=request.user)
        messages.success(request, _('Two-factor authentication is now enabled for your account.'))
        request.user.send_security_notice([_('Two-factor authentication has been enabled.')])
        request.user.update_session_token()
        update_session_auth_hash(request, request.user)
        return redirect(reverse('eventyay_common:account.2fa'))


class TwoFactorAuthDisableView(TwoFactorAuthPageMixin, TemplateView):
    template_name = 'eventyay_common/account/2fa-disable.html'

    def post(self, request: HttpRequest, *args, **kwargs):
        request.user.require_2fa = False
        request.user.save()
        request.user.log_action('pretix.user.settings.2fa.disabled', user=request.user)
        messages.success(request, _('Two-factor authentication is now disabled for your account.'))
        request.user.send_security_notice([_('Two-factor authentication has been disabled.')])
        request.user.update_session_token()
        update_session_auth_hash(request, request.user)
        return redirect(reverse('eventyay_common:account.2fa'))


class TwoFactorAuthDeviceAddView(TwoFactorAuthPageMixin, FormView):
    form_class = User2FADeviceAddForm
    template_name = 'eventyay_common/account/2fa-add.html'

    def form_valid(self, form: BaseForm) -> HttpResponse:
        device_type = form.cleaned_data['devicetype']
        name = form.cleaned_data['name']
        if device_type == 'totp':
            dev = TOTPDevice.objects.create(user=self.request.user, confirmed=False, name=name)
        elif device_type == 'webauthn':
            if not self.request.is_secure():
                messages.error(self.request, _('Security devices are only available if pretix is served via HTTPS.'))
                return self.get(self.request, self.args, self.kwargs)
            dev = WebAuthnDevice.objects.create(user=self.request.user, confirmed=False, name=name)
        next_url_name = f'eventyay_common:account.2fa.confirm.{device_type}'
        return redirect(reverse(next_url_name, kwargs={'device_id': dev.pk}))

    def form_invalid(self, form: BaseForm) -> HttpResponse:
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)


class TwoFactorAuthDeviceConfirmTOTPView(TwoFactorAuthPageMixin, TemplateView):
    template_name = 'eventyay_common/account/2fa-confirm-totp.html'

    @cached_property
    def device(self) -> TOTPDevice:
        return get_object_or_404(TOTPDevice, user=self.request.user, pk=self.kwargs['device_id'], confirmed=False)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()

        secret = base64.b32encode(self.device.bin_key).decode('utf-8')
        ctx['secret'] = secret
        ctx['secretGrouped'] = '  '.join([secret.lower()[(i * 4) : (i + 1) * 4] for i in range(len(secret) // 4)])
        label = f'{settings.INSTANCE_NAME}: {self.request.user.email}'
        ctx['qrdata'] = 'otpauth://totp/{}?{}'.format(
            quote(label), urlencode({'issuer': settings.INSTANCE_NAME, 'secret': secret, 'digits': self.device.digits})
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
            user.log_action(
                'pretix.user.settings.2fa.device.added',
                user=user,
                data={'id': self.device.pk, 'name': self.device.name, 'devicetype': 'totp'},
            )
            notices = [_('A new two-factor authentication device has been added to your account.')]
            if activate == 'on' and not user.require_2fa:
                user.require_2fa = True
                user.save()
                user.log_action('pretix.user.settings.2fa.enabled', user=user)
                notices.append(_('Two-factor authentication has been enabled.'))
            user.send_security_notice(notices)
            user.update_session_token()
            update_session_auth_hash(self.request, user)

            note = ''
            if not user.require_2fa:
                note = ' ' + gettext(
                    'Please note that you still need to enable two-factor authentication for your '
                    'account using the buttons below to make a second factor required for logging '
                    'into your account.'
                )
            messages.success(request, gettext('The device has been verified and can now be used.') + note)
            return redirect(reverse('eventyay_common:account.2fa'))
        messages.error(
            request,
            gettext(
                'The code you entered was not valid. If this problem persists, please check '
                'that the date and time of your phone are configured correctly.'
            ),
        )
        return redirect(reverse('eventyay_common:account.2fa.confirm.totp', kwargs={'device_id': self.device.pk}))


class TwoFactorAuthDeviceConfirmWebAuthnView(TwoFactorAuthPageMixin, TemplateView):
    template_name = 'eventyay_common/account/2fa-confirm-webauthn.html'

    @cached_property
    def device(self):
        return get_object_or_404(WebAuthnDevice, user=self.request.user, pk=self.kwargs['device_id'], confirmed=False)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['device'] = self.device
        session = self.request.session

        if 'webauthn_register_ukey' in session:
            del session['webauthn_register_ukey']
        if 'webauthn_challenge' in session:
            del session['webauthn_challenge']

        challenge = generate_challenge()
        ukey = generate_user_handle()

        session['webauthn_challenge'] = base64.b64encode(challenge).decode()
        session['webauthn_register_ukey'] = base64.b64encode(ukey).decode()

        devices = [
            device.webauthndevice for device in WebAuthnDevice.objects.filter(confirmed=True, user=self.request.user)
        ] + [device.webauthndevice for device in U2FDevice.objects.filter(confirmed=True, user=self.request.user)]
        make_credential_options = webauthn.generate_registration_options(
            rp_id=get_webauthn_rp_id(),
            rp_name=get_webauthn_rp_id(),
            user_id=ukey,
            user_name=self.request.user.email,
            challenge=challenge,
            exclude_credentials=devices,
        )
        ctx['jsondata'] = webauthn.options_to_json(make_credential_options)

        return ctx

    def post(self, request: HttpRequest, *args, **kwargs):
        session = request.session
        try:
            challenge = session['webauthn_challenge']
            ukey = session['webauthn_register_ukey']
            resp = json.loads(request.POST.get('token'))
            registration_verification = webauthn.verify_registration_response(
                credential=resp,
                expected_challenge=base64.b64decode(challenge),
                expected_rp_id=get_webauthn_rp_id(),
                expected_origin=settings.SITE_URL,
            )
            # Check that the credentialId is not yet registered to any other user.
            # If registration is requested for a credential that is already registered
            # to a different user, the Relying Party SHOULD fail this registration
            # ceremony, or it MAY decide to accept the registration, e.g. while deleting
            # the older registration.
            credential_id_exists = WebAuthnDevice.objects.filter(
                credential_id=registration_verification.credential_id
            ).first()
            if credential_id_exists:
                messages.error(request, _('This security device is already registered.'))
                return redirect(
                    reverse('eventyay_common:account.2fa.confirm.webauthn', kwargs={'device_id': self.device.pk})
                )

            device = self.device

            device.credential_id = websafe_encode(registration_verification.credential_id)
            device.ukey = websafe_encode(ukey)
            device.pub_key = websafe_encode(registration_verification.credential_public_key)
            device.sign_count = registration_verification.sign_count
            device.rp_id = get_webauthn_rp_id()
            device.icon_url = settings.SITE_URL
            device.confirmed = True
            device.save()
            request.user.log_action(
                'pretix.user.settings.2fa.device.added',
                user=self.request.user,
                data={
                    'id': device.pk,
                    'devicetype': 'u2f',
                    'name': device.name,
                },
            )
            notices = [_('A new two-factor authentication device has been added to your account.')]
            activate = request.POST.get('activate', '')
            if activate == 'on' and not request.user.require_2fa:
                request.user.require_2fa = True
                request.user.save()
                request.user.log_action('pretix.user.settings.2fa.enabled', user=request.user)
                notices.append(_('Two-factor authentication has been enabled.'))
            request.user.send_security_notice(notices)
            request.user.update_session_token()
            update_session_auth_hash(request, request.user)

            note = ''
            if not request.user.require_2fa:
                note = ' ' + gettext(
                    'Please note that you still need to enable two-factor authentication for your '
                    'account using the buttons below to make a second factor required for logging '
                    'into your account.'
                )
            messages.success(request, gettext('The device has been verified and can now be used.') + note)
            return redirect(reverse('eventyay_common:account.2fa'))
        except Exception as e:
            msg = f'WebAuthn registration failed: {e}'
            logger.exception(msg, exc_info=True)
            messages.error(request, _('The registration could not be completed. Please try again.'))
            return redirect(
                reverse('eventyay_common:account.2fa.confirm.webauthn', kwargs={'device_id': self.device.pk})
            )


class TwoFactorAuthDeviceDeleteView(TwoFactorAuthPageMixin, TemplateView):
    template_name = 'eventyay_common/account/2fa-delete.html'

    @cached_property
    def device(self):
        device_type = self.kwargs['devicetype']
        device_id = self.kwargs['device_id']
        if device_type == 'totp':
            return get_object_or_404(TOTPDevice, user=self.request.user, pk=device_id, confirmed=True)
        elif device_type == 'webauthn':
            return get_object_or_404(WebAuthnDevice, user=self.request.user, pk=device_id, confirmed=True)
        elif device_type == 'u2f':
            return get_object_or_404(U2FDevice, user=self.request.user, pk=device_id, confirmed=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['device'] = self.device
        return ctx

    def post(self, request: HttpRequest, *args, **kwargs):
        request.user.log_action(
            'pretix.user.settings.2fa.device.deleted',
            user=request.user,
            data={'id': self.device.pk, 'name': self.device.name, 'devicetype': self.kwargs['devicetype']},
        )
        device = self.device
        device.delete()
        msgs = [_('A two-factor authentication device has been removed from your account.')]
        if not any(dt.objects.filter(user=request.user, confirmed=True) for dt in REAL_DEVICE_TYPES):
            request.user.require_2fa = False
            request.user.save()
            request.user.log_action('pretix.user.settings.2fa.disabled', user=request.user)
            msgs.append(_('Two-factor authentication has been disabled.'))

        request.user.send_security_notice(msgs)
        request.user.update_session_token()
        update_session_auth_hash(request, request.user)
        messages.success(request, _('The device has been removed.'))
        return redirect(reverse('eventyay_common:account.2fa'))


class TwoFactorAuthRegenerateEmergencyView(TwoFactorAuthPageMixin, TemplateView):
    template_name = 'eventyay_common/account/2fa-regenemergency.html'

    def post(self, request: HttpRequest, *args, **kwargs):
        StaticDevice.objects.filter(user=request.user, name='emergency').delete()
        d = StaticDevice.objects.create(user=request.user, name='emergency')
        for _i in range(10):
            d.token_set.create(token=get_random_string(length=12, allowed_chars='1234567890'))
        request.user.log_action('eventyay_common:account.2fa.regenemergency', user=request.user)
        request.user.send_security_notice([_('Your two-factor emergency codes have been regenerated.')])
        request.user.update_session_token()
        update_session_auth_hash(request, request.user)
        messages.success(
            request,
            _(
                'Your emergency codes have been newly generated. Remember to store them in a safe '
                'place in case you lose access to your devices.'
            ),
        )
        return redirect(reverse('eventyay_common:account.2fa'))


def get_webauthn_rp_id():
    return urlparse(settings.SITE_URL).hostname
