import base64
import json
import logging
import time
from urllib.parse import quote

import webauthn
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import ListView, TemplateView, UpdateView
from webauthn.helpers import generate_challenge

from eventyay.base.auth import get_auth_backends
from eventyay.base.forms.auth import ReauthForm
from eventyay.base.models import (
    Order,
    U2FDevice,
    WebAuthnDevice,
)
from eventyay.base.models.auth import StaffSession
from eventyay.control.forms.organizer_forms.user_orders_form import (
    UserOrderFilterForm,
)
from eventyay.control.forms.users import StaffSessionForm
from eventyay.control.permissions import (
    AdministratorPermissionRequiredMixin,
    StaffMemberRequiredMixin,
)
from eventyay.eventyay_common.views.auth import get_u2f_appid, get_webauthn_rp_id

logger = logging.getLogger(__name__)


class RecentAuthenticationRequiredMixin:
    max_time = 3600

    def dispatch(self, request, *args, **kwargs):
        tdelta = time.time() - request.session.get('eventyay_auth_login_time', 0)
        if tdelta > self.max_time:
            return redirect(reverse('control:user.reauth') + '?next=' + quote(request.get_full_path()))
        return super().dispatch(request, *args, **kwargs)


class ReauthView(TemplateView):
    template_name = 'pretixcontrol/user/reauth.html'

    def post(self, request, *args, **kwargs):
        r = request.POST.get('webauthn', '')
        valid = False

        if 'webauthn_challenge' in self.request.session and r.startswith('{'):
            challenge = self.request.session['webauthn_challenge']

            resp = json.loads(r)
            try:
                devices = [WebAuthnDevice.objects.get(user=self.request.user, credential_id=resp.get('id'))]
            except WebAuthnDevice.DoesNotExist:
                devices = U2FDevice.objects.filter(user=self.request.user)

            for d in devices:
                credential_current_sign_count = d.sign_count if isinstance(d, WebAuthnDevice) else 0
                try:
                    webauthn_assertion_response = webauthn.verify_authentication_response(
                        credential=resp,
                        expected_challenge=base64.b64decode(challenge),
                        expected_rp_id=get_webauthn_rp_id(self.request),
                        expected_origin=settings.SITE_URL,
                        credential_public_key=d.webauthnpubkey,
                        credential_current_sign_count=credential_current_sign_count,
                    )
                    sign_count = webauthn_assertion_response.new_sign_count
                    if sign_count < credential_current_sign_count:
                        raise Exception('Possible replay attack, sign count not higher')
                except Exception:
                    if isinstance(d, U2FDevice):
                        try:
                            webauthn_assertion_response = webauthn.verify_authentication_response(
                                credential=resp,
                                expected_challenge=base64.b64decode(challenge),
                                expected_rp_id=get_u2f_appid(self.request),
                                expected_origin=settings.SITE_URL,
                                credential_public_key=d.webauthnpubkey,
                                credential_current_sign_count=credential_current_sign_count,
                            )
                            if webauthn_assertion_response.new_sign_count < 1:
                                raise Exception('Possible replay attack, sign count set')
                        except Exception:
                            logger.exception('U2F login failed')
                        else:
                            valid = True
                            break
                    else:
                        logger.exception('Webauthn login failed')
                else:
                    if isinstance(d, WebAuthnDevice):
                        d.sign_count = sign_count
                        d.save()
                    valid = True
                    break

        valid = valid or self.form.is_valid()

        if valid:
            t = int(time.time())
            request.session['eventyay_auth_login_time'] = t
            request.session['eventyay_auth_last_used'] = t
            next_url = get_auth_backends()[request.user.auth_backend].get_next_url(request)
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
                return redirect(next_url)
            return redirect(reverse('control:index'))
        else:
            messages.error(request, _('The password you entered was invalid, please try again.'))
            return self.get(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        backend = get_auth_backends()[request.user.auth_backend]
        u = backend.request_authenticate(request)
        if u and u == request.user:
            next_url = backend.get_next_url(request)
            t = int(time.time())
            request.session['eventyay_auth_login_time'] = t
            request.session['pretix_auth_last_used'] = t
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
                return redirect(next_url)
            return redirect(reverse('control:index'))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        if 'webauthn_challenge' in self.request.session:
            del self.request.session['webauthn_challenge']
        challenge = generate_challenge()
        self.request.session['webauthn_challenge'] = base64.b64encode(challenge).decode()
        devices = [
            device.webauthndevice for device in WebAuthnDevice.objects.filter(confirmed=True, user=self.request.user)
        ] + [device.webauthndevice for device in U2FDevice.objects.filter(confirmed=True, user=self.request.user)]
        if devices:
            auth_options = webauthn.generate_authentication_options(
                rp_id=get_webauthn_rp_id(self.request),
                challenge=challenge,
                allow_credentials=devices,
            )
            j = json.loads(webauthn.options_to_json(auth_options))
            j['extensions'] = {'appid': get_u2f_appid(self.request)}
            ctx['jsondata'] = json.dumps(j)
        ctx['form'] = self.form
        return ctx

    @cached_property
    def form(self):
        return ReauthForm(
            user=self.request.user,
            backend=get_auth_backends()[self.request.user.auth_backend],
            request=self.request,
            data=self.request.POST if self.request.method == 'POST' else None,
            initial={
                'email': self.request.user.email,
            },
        )


class StartStaffSession(StaffMemberRequiredMixin, RecentAuthenticationRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/user/staff_session_start.html'

    def post(self, request, *args, **kwargs):
        if not request.user.has_active_staff_session(request.session.session_key):
            StaffSession.objects.create(user=request.user, session_key=request.session.session_key)

        if 'next' in request.GET and url_has_allowed_host_and_scheme(request.GET.get('next'), allowed_hosts=None):
            return redirect(request.GET.get('next'))
        else:
            return redirect(reverse('control:index'))


class StopStaffSession(StaffMemberRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        session = StaffSession.objects.filter(
            date_end__isnull=True,
            session_key=request.session.session_key,
            user=request.user,
        ).first()
        if not session:
            return redirect(reverse('control:index'))

        session.date_end = now()
        session.save()
        return redirect(reverse('eventyay_admin:admin.user.sudo.edit', kwargs={'id': session.pk}))


class StaffSessionList(AdministratorPermissionRequiredMixin, ListView):
    context_object_name = 'sessions'
    template_name = 'pretixcontrol/admin/user/staff_session_list.html'
    paginate_by = 25
    model = StaffSession

    def get_queryset(self):
        return StaffSession.objects.select_related('user').order_by('-date_start')


class EditStaffSession(StaffMemberRequiredMixin, UpdateView):
    context_object_name = 'session'
    template_name = 'pretixcontrol/admin/user/staff_session_edit.html'
    form_class = StaffSessionForm

    def get_success_url(self):
        return reverse('eventyay_admin:admin.user.sudo.edit', kwargs={'id': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['logs'] = self.object.logs.select_related('impersonating')
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _('Your comment has been saved.'))
        return super().form_valid(form)

    def get_object(self, queryset=None):
        if self.request.user.has_active_staff_session(self.request.session.session_key):
            return get_object_or_404(StaffSession, pk=self.kwargs['id'])
        else:
            return get_object_or_404(StaffSession, pk=self.kwargs['id'], user=self.request.user)


class UserOrdersView(ListView):
    template_name = 'pretixcontrol/user/orders.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        qs = (
            Order.objects.filter(Q(email__iexact=self.request.user.email)).select_related('event').order_by('-datetime')
        )

        # Filter by event if provided
        event_id = self.request.GET.get('event')
        if event_id:
            qs = qs.filter(event_id=event_id)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = UserOrderFilterForm(self.request.GET or None, user=self.request.user)
        return ctx
