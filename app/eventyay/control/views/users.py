import json
import logging
from contextlib import contextmanager

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    get_user_model,
    load_backend,
    login,
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import DatabaseError, transaction
from django.db.models import CharField, Exists, OuterRef, Value
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, TemplateView
from hijack import signals
from oauth2_provider.decorators import protected_resource

from allauth.socialaccount import providers
from allauth.socialaccount.models import SocialAccount

from eventyay.base.auth import get_auth_backends
from eventyay.base.models import User
from eventyay.base.services.mail import SendMailException
from eventyay.base.settings import GlobalSettingsObject
from eventyay.control.forms.filter import UserFilterForm
from eventyay.base.services.user import (
    admin_users_list_q,
    platform_user_video_display_name,
    resolve_video_display_names_by_contact_emails,
)
from eventyay.control.forms.users import UserEditForm
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.control.views import CreateView, UpdateView
from eventyay.control.views.user import RecentAuthenticationRequiredMixin

logger = logging.getLogger(__name__)


def get_used_backend(request):
    backend_str = request.session[BACKEND_SESSION_KEY]
    backend = load_backend(backend_str)
    return backend


@contextmanager
def keep_session_age(session):
    try:
        session_expiry = session['_session_expiry']
    except KeyError:
        yield
    else:
        yield
        session['_session_expiry'] = session_expiry


class UserListView(AdministratorPermissionRequiredMixin, ListView):
    template_name = 'pretixcontrol/admin/users/index.html'
    context_object_name = 'users'
    paginate_by = 30

    _ACTION_HANDLERS = {
        'toggle_verified': '_handle_toggle_verified',
        'toggle_admin': '_handle_toggle_admin',
        'toggle_spam': '_handle_toggle_spam',
        'resend_verification': '_handle_resend_verification',
        'reset_password': '_handle_reset_password',
    }

    def get_queryset(self):
        qs = (
            User.objects.filter(admin_users_list_q())
            .annotate(
                is_email_verified=Exists(
                    EmailAddress.objects.filter(user=OuterRef('pk'), primary=True, verified=True)
                ),
                admin_list_email=Coalesce(
                    'email',
                    KeyTextTransform('contact_email', 'profile'),
                    Value(''),
                    output_field=CharField(),
                ),
                admin_list_fullname=Coalesce(
                    'fullname',
                    KeyTextTransform('display_name', 'profile'),
                    Value(''),
                    output_field=CharField(),
                ),
            )
        )
        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        users = ctx[self.context_object_name]
        emails = [
            (u.admin_list_email or '').strip().lower()
            for u in users
            if u.admin_list_email and not u.event_id
        ]
        video_names = resolve_video_display_names_by_contact_emails(emails)
        for user in users:
            if user.event_id:
                user.video_username = ''
            else:
                user.video_username = platform_user_video_display_name(user, video_names)
        return ctx

    @cached_property
    def filter_form(self):
        return UserFilterForm(data=self.request.GET)

    def post(self, request, *args, **kwargs):
        data = request.POST
        if not data:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except (ValueError, AttributeError):
                data = {}

        action = data.get('action')
        user_id = data.get('user_id')

        if not user_id or not action:
            msg = str(_('Missing user_id or action.'))
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': msg}, status=400)
            messages.error(request, msg)
            return redirect(reverse('eventyay_admin:admin.users'))

        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            msg = str(_('Invalid user_id.'))
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': msg}, status=400)
            messages.error(request, msg)
            return redirect(reverse('eventyay_admin:admin.users'))

        try:
            target_user = User.objects.get(pk=user_id, event__isnull=True)
        except User.DoesNotExist:
            msg = str(_('User not found.'))
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': msg}, status=404)
            messages.error(request, msg)
            return redirect(reverse('eventyay_admin:admin.users'))

        handler_name = self._ACTION_HANDLERS.get(action)
        if not handler_name:
            msg = str(_('Unknown action.'))
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': msg}, status=400)
            messages.error(request, msg)
            return redirect(reverse('eventyay_admin:admin.users'))

        handler = getattr(self, handler_name)
        return handler(request, target_user)

    def _get_or_create_primary_email(self, target_user):
        primary_email = EmailAddress.objects.filter(user=target_user, primary=True).first()
        if not primary_email and target_user.email:
            primary_email = EmailAddress.objects.filter(user=target_user, email__iexact=target_user.email).first()
            if primary_email:
                primary_email.primary = True
                primary_email.save(update_fields=['primary'])
            else:
                try:
                    with transaction.atomic():
                        primary_email = EmailAddress.objects.create(
                            user=target_user,
                            email=target_user.email,
                            primary=True,
                            verified=False
                        )
                except DatabaseError:
                    primary_email = EmailAddress.objects.filter(user=target_user, email__iexact=target_user.email).first()
        return primary_email

    def _handle_toggle_verified(self, request, target_user):
        if not target_user.email:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'status': 'error', 'message': str(_('This user has no email address.'))},
                    status=400,
                )
            messages.error(request, _('This user has no email address.'))
            return redirect(reverse('eventyay_admin:admin.users'))

        with transaction.atomic():
            primary_email = self._get_or_create_primary_email(target_user)

            if not primary_email:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse(
                        {'status': 'error', 'message': str(_('This user has no primary email address.'))},
                        status=400,
                    )
                messages.error(request, _('This user has no primary email address.'))
                return redirect(reverse('eventyay_admin:admin.users'))

            from django.db.models import Case, When, Value, BooleanField
            EmailAddress.objects.filter(pk=primary_email.pk).update(
                verified=Case(
                    When(verified=True, then=Value(False)),
                    default=Value(True),
                    output_field=BooleanField()
                )
            )
            primary_email.refresh_from_db()
            new_verified_status = primary_email.verified
        target_user.log_action(
            'eventyay.user.settings.changed',
            user=request.user,
            data={'email_verified': new_verified_status},
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'ok',
                'is_verified': new_verified_status,
            })
        action_label = _('verified') if new_verified_status else _('unverified')
        messages.success(
            request,
            _('User %(email)s has been marked as %(action)s.') % {
                'email': target_user.email or str(target_user),
                'action': action_label,
            },
        )
        return redirect(reverse('eventyay_admin:admin.users'))

    def _handle_toggle_admin(self, request, target_user):
        if target_user == request.user:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'status': 'error', 'message': str(_('You cannot change your own admin status.'))},
                    status=400,
                )
            messages.error(request, _('You cannot change your own admin status.'))
            return redirect(reverse('eventyay_admin:admin.users'))

        with transaction.atomic():
            user_to_update = User.objects.select_for_update().get(pk=target_user.pk)
            user_to_update.is_staff = not user_to_update.is_staff
            update_fields = ['is_staff']
            if user_to_update.is_staff and user_to_update.is_spam:
                user_to_update.is_spam = False
                update_fields.append('is_spam')
            user_to_update.save(update_fields=update_fields)
            target_user.is_staff = user_to_update.is_staff
            target_user.is_spam = user_to_update.is_spam

        target_user.log_action(
            'eventyay.user.settings.changed',
            user=request.user,
            data={'is_staff': target_user.is_staff, 'is_spam': target_user.is_spam},
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'ok',
                'is_staff': target_user.is_staff,
                'is_spam': target_user.is_spam,
            })
        action_label = _('granted admin') if target_user.is_staff else _('removed admin')
        messages.success(
            request,
            _('Admin status for %(email)s has been %(action)s.') % {
                'email': target_user.email or str(target_user),
                'action': action_label,
            },
        )
        return redirect(reverse('eventyay_admin:admin.users'))

    def _handle_toggle_spam(self, request, target_user):
        if target_user == request.user:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'status': 'error', 'message': str(_('You cannot mark yourself as spam.'))},
                    status=400,
                )
            messages.error(request, _('You cannot mark yourself as spam.'))
            return redirect(reverse('eventyay_admin:admin.users'))

        with transaction.atomic():
            user_to_update = User.objects.select_for_update().get(pk=target_user.pk)
            if user_to_update.is_staff or user_to_update.is_superuser:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse(
                        {'status': 'error', 'message': str(_('Administrators cannot be marked as spam.'))},
                        status=400,
                    )
                messages.error(request, _('Administrators cannot be marked as spam.'))
                return redirect(reverse('eventyay_admin:admin.users'))

            user_to_update.is_spam = not user_to_update.is_spam
            user_to_update.save(update_fields=['is_spam'])
            if user_to_update.is_spam:
                # Revoke active sessions upon flagging as spam.
                user_to_update.update_session_token()
            target_user.is_spam = user_to_update.is_spam

        target_user.log_action(
            'eventyay.user.settings.changed',
            user=request.user,
            data={'is_spam': target_user.is_spam},
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok', 'is_spam': target_user.is_spam})
        action_label = _('marked as spam') if target_user.is_spam else _('unmarked as spam')
        messages.success(
            request,
            _('User %(email)s has been %(action)s.') % {
                'email': target_user.email or str(target_user),
                'action': action_label,
            },
        )
        return redirect(reverse('eventyay_admin:admin.users'))

    def _handle_resend_verification(self, request, target_user):
        if not target_user.email:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'status': 'error', 'message': str(_('This user has no email address.'))},
                    status=400,
                )
            messages.error(request, _('This user has no email address.'))
            return redirect(reverse('eventyay_admin:admin.users'))

        try:
            with transaction.atomic():
                email_address = self._get_or_create_primary_email(target_user)
                if not email_address:
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse(
                            {'status': 'error', 'message': str(_('This user has no primary email address.'))},
                            status=400,
                        )
                    messages.error(request, _('This user has no primary email address.'))
                    return redirect(reverse('eventyay_admin:admin.users'))
                is_verified = email_address.verified

            if is_verified:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse(
                        {'status': 'error', 'message': str(_('This user is already verified.'))},
                        status=400,
                    )
                messages.warning(request, _('This user is already verified.'))
                return redirect(reverse('eventyay_admin:admin.users'))

            try:
                email_address.send_confirmation(request)
            except Exception as e:
                raise SendMailException(str(e)) from e
        except SendMailException:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'status': 'error', 'message': str(_('There was an error sending the verification email.'))},
                    status=500,
                )
            messages.error(request, _('There was an error sending the verification email.'))
            return redirect(reverse('eventyay_admin:admin.users'))

        target_user.log_action(
            'eventyay.control.auth.user.verification_email_sent',
            user=request.user,
            data={'target_user': target_user.pk},
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'ok',
                'message': str(_('Verification email sent successfully.'))
            })
        messages.success(
            request,
            _('Verification email sent to %(email)s.') % {'email': target_user.email},
        )
        return redirect(reverse('eventyay_admin:admin.users'))

    def _handle_reset_password(self, request, target_user):
        if not target_user.email:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'status': 'error', 'message': str(_('This user has no email address.'))},
                    status=400,
                )
            messages.error(request, _('This user has no email address.'))
            return redirect(reverse('eventyay_admin:admin.users'))

        try:
            target_user.send_password_reset(request)
        except SendMailException:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'status': 'error', 'message': str(_('There was an error sending the mail. Please try again later.'))},
                    status=500,
                )
            messages.error(request, _('There was an error sending the mail. Please try again later.'))
            return redirect(reverse('eventyay_admin:admin.users'))

        target_user.log_action('eventyay.control.auth.user.forgot_password.mail_sent', user=request.user)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'ok',
                'message': str(_('Password reset email sent successfully.'))
            })
        messages.success(
            request,
            _('Password reset email sent to %(email)s.') % {'email': target_user.email},
        )
        return redirect(reverse('eventyay_admin:admin.users'))


class UserEditView(AdministratorPermissionRequiredMixin, RecentAuthenticationRequiredMixin, UpdateView):
    template_name = 'pretixcontrol/admin/users/form.html'
    context_object_name = 'edit_user'
    form_class = UserEditForm

    def get_object(self, queryset=None):
        return get_object_or_404(User, pk=self.kwargs.get('id'), event__isnull=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['teams'] = self.object.teams.select_related('organizer')
        b = get_auth_backends()
        ctx['backend'] = (
            b[self.object.auth_backend].verbose_name if self.object.auth_backend in b else self.object.auth_backend
        )

        gs = GlobalSettingsObject()
        login_providers = gs.settings.get('login_providers', as_type=dict) or {}
        active_providers = {
            key for key, cfg in login_providers.items()
            if isinstance(cfg, dict) and cfg.get('state') and cfg.get('client_id') and cfg.get('secret')
        }
        ctx['sso_providers_active'] = bool(active_providers)

        provider_labels = dict(providers.registry.as_choices())
        social_accounts = SocialAccount.objects.filter(user=self.object).order_by('provider')
        connected_accounts = []
        for sa in social_accounts:
            extra = sa.extra_data or {}
            connected_accounts.append({
                'provider': sa.provider,
                'provider_label': provider_labels.get(sa.provider, sa.provider),
                'uid': sa.uid,
                'username': extra.get('username', ''),
                'email': extra.get('email', ''),
                'date_joined': sa.date_joined,
                'is_active_provider': sa.provider in active_providers,
            })
        ctx['connected_accounts'] = connected_accounts

        return ctx

    def get_success_url(self):
        return reverse('eventyay_admin:admin.users.edit', kwargs=self.kwargs)

    def form_valid(self, form):
        messages.success(self.request, _('Your changes have been saved.'))

        data = {}
        for k in form.changed_data:
            if k != 'new_pw_repeat':
                if 'new_pw' == k:
                    data['new_pw'] = True
                else:
                    data[k] = form.cleaned_data[k]

        sup = super().form_valid(form)

        if 'require_2fa' in form.changed_data and form.cleaned_data['require_2fa']:
            self.object.log_action('eventyay.user.settings.2fa.enabled', user=self.request.user)
        elif 'require_2fa' in form.changed_data and not form.cleaned_data['require_2fa']:
            self.object.log_action('eventyay.user.settings.2fa.disabled', user=self.request.user)
        self.object.log_action('eventyay.user.settings.changed', user=self.request.user, data=data)

        return sup


class UserResetView(AdministratorPermissionRequiredMixin, RecentAuthenticationRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect(reverse('eventyay_admin:admin.users.edit', kwargs=self.kwargs))

    def post(self, request, *args, **kwargs):
        self.object = get_object_or_404(User, pk=self.kwargs.get('id'))
        try:
            self.object.send_password_reset(request)
        except SendMailException:
            messages.error(
                request,
                _('There was an error sending the mail. Please try again later.'),
            )
            return redirect(self.get_success_url())

        self.object.log_action('eventyay.control.auth.user.forgot_password.mail_sent', user=request.user)
        messages.success(request, _('We sent out an e-mail containing further instructions.'))
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('eventyay_admin:admin.users.edit', kwargs=self.kwargs)


class UserAnonymizeView(
    AdministratorPermissionRequiredMixin,
    RecentAuthenticationRequiredMixin,
    TemplateView,
):
    template_name = 'pretixcontrol/admin/users/anonymize.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['edit_user'] = get_object_or_404(User, pk=self.kwargs.get('id'))
        return ctx

    def get_success_url(self):
        return reverse('eventyay_admin:admin.users')

    def get_error_url(self):
        return reverse('eventyay_admin:admin.users.edit', kwargs=self.kwargs)

    def post(self, request, *args, **kwargs):
        self.object = get_object_or_404(User, pk=self.kwargs.get('id'))
        try:
            with transaction.atomic():
                self.object.log_action('eventyay.user.anonymized', user=request.user)
                self.object.email = '{}@disabled.eventyay.com'.format(self.object.pk)
                self.object.fullname = ''
                self.object.is_active = False
                self.object.notifications_send = False
                self.object.save()
                for le in self.object.all_logentries.filter(action_type='eventyay.user.settings.changed'):
                    d = le.parsed_data
                    if 'email' in d:
                        d['email'] = '█'
                    if 'fullname' in d:
                        d['fullname'] = '█'
                    le.data = json.dumps(d)
                    le.shredded = True
                    le.save(update_fields=['data', 'shredded'])
        except DatabaseError:
            logger.exception('Failed to anonymize user %s from admin user page.', self.object.pk)
            messages.error(request, _('The user could not be anonymized. Please try again later.'))
            return redirect(self.get_error_url())
        else:
            messages.success(request, _('User has been anonymized successfully.'))
            return redirect(self.get_success_url())


class UserImpersonateView(AdministratorPermissionRequiredMixin, RecentAuthenticationRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect(reverse('eventyay_admin:admin.users.edit', kwargs=self.kwargs))

    def post(self, request, *args, **kwargs):
        self.object = get_object_or_404(User, pk=self.kwargs.get('id'))
        self.request.user.log_action(
            'eventyay.control.auth.user.impersonated',
            user=request.user,
            data={'other': self.kwargs.get('id'), 'other_email': self.object.email},
        )
        oldkey = request.session.session_key
        hijacker = request.user
        hijacked = self.object

        hijack_history = request.session.get('hijack_history', [])
        hijack_history.append(request.user._meta.pk.value_to_string(hijacker))

        backend = get_used_backend(request)
        backend = f'{backend.__module__}.{backend.__class__.__name__}'

        with signals.no_update_last_login(), keep_session_age(request.session):
            login(request, hijacked, backend=backend)

        request.session['hijack_history'] = hijack_history

        signals.hijack_started.send(
            sender=None,
            request=request,
            hijacker=hijacker,
            hijacked=hijacked,
        )
        request.session['hijacker_session'] = oldkey
        return redirect(reverse('control:index'))


class UserImpersonateStopView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        impersonated = request.user
        hijs = request.session['hijacker_session']
        hijack_history = request.session.get('hijack_history', [])
        hijacked = request.user
        user_pk = hijack_history.pop()
        hijacker = get_object_or_404(get_user_model(), pk=user_pk)
        backend = get_used_backend(request)
        backend = f'{backend.__module__}.{backend.__class__.__name__}'
        with signals.no_update_last_login(), keep_session_age(request.session):
            login(request, hijacker, backend=backend)

        request.session['hijack_history'] = hijack_history

        signals.hijack_ended.send(
            sender=None,
            request=request,
            hijacker=hijacker,
            hijacked=hijacked,
        )
        ss = request.user.get_active_staff_session(hijs)
        if ss:
            request.session.save()
            ss.session_key = request.session.session_key
            ss.save()

        request.user.log_action(
            'eventyay.control.auth.user.impersonate_stopped',
            user=request.user,
            data={'other': impersonated.pk, 'other_email': impersonated.email},
        )
        return redirect(reverse('control:index'))


class UserCreateView(AdministratorPermissionRequiredMixin, RecentAuthenticationRequiredMixin, CreateView):
    template_name = 'pretixcontrol/admin/users/create.html'
    context_object_name = 'user'
    form_class = UserEditForm

    def get_form(self, form_class=None):
        f = super().get_form(form_class)
        f.fields['new_pw'].required = True
        f.fields['new_pw_repeat'].required = True
        return f

    def get_initial(self):
        i = super().get_initial()
        i['timezone'] = settings.TIME_ZONE
        return i

    def get_success_url(self):
        return reverse('eventyay_admin:admin.users')

    def form_valid(self, form):
        messages.success(self.request, _('The new user has been created.'))
        return super().form_valid(form)


@require_http_methods(['GET'])
@protected_resource()  # Ensures the endpoint is protected by OAuth2
def user_info(request):
    """
    Return user information for the authenticated user.
    """
    user = request.resource_owner
    user_data = {
        'email': user.email,
        'name': user.get_full_name(),
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'locale': user.locale,
        'timezone': user.timezone,
        # Add more user fields as necessary
    }
    return JsonResponse(user_data)
