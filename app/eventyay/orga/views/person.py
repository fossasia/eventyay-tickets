import urllib

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, View
from django_context_decorator import context
from django_scopes import scopes_disabled

from eventyay.api.versions import CURRENT_VERSION
from eventyay.common.text.phrases import phrases
from eventyay.common.views import is_form_bound
from eventyay.person.forms import AuthTokenForm, LoginInfoForm, OrgaProfileForm


class UserSettings(TemplateView):
    form_class = LoginInfoForm
    template_name = 'orga/user.html'

    def get_success_url(self) -> str:
        return reverse('orga:user.view')

    @context
    @cached_property
    def login_form(self):
        return LoginInfoForm(
            user=self.request.user,
            data=self.request.POST if is_form_bound(self.request, 'login') else None,
        )

    @context
    def current_version(self):
        return CURRENT_VERSION

    @context
    @cached_property
    def profile_form(self):
        return OrgaProfileForm(
            instance=self.request.user,
            data=self.request.POST if is_form_bound(self.request, 'profile') else None,
        )

    @context
    @cached_property
    def token_form(self):
        return AuthTokenForm(
            user=self.request.user,
            data=self.request.POST if is_form_bound(self.request, 'token') else None,
        )

    def post(self, request, *args, **kwargs):
        if self.login_form.is_bound and self.login_form.is_valid():
            self.login_form.save()
            messages.success(request, phrases.base.saved)
            request.user.log_action('eventyay.user.password.update')
        elif self.profile_form.is_bound and self.profile_form.is_valid():
            self.profile_form.save()
            messages.success(request, phrases.base.saved)
            request.user.log_action('eventyay.user.profile.update')
        elif self.token_form.is_bound and self.token_form.is_valid():
            token = self.token_form.save()
            if token:
                messages.success(
                    request,
                    _('This is your new API token. Please make sure to save it, as it will not be shown again:')
                    + f' {token.token}',
                )
                request.user.log_action('eventyay.user.token.create', data=token.serialize())
        elif token_id := request.POST.get('tokenupgrade'):
            token = request.user.api_tokens.filter(pk=token_id).first()
            token.version = CURRENT_VERSION
            token.save()
            request.user.log_action('eventyay.user.token.upgrade', data=token.serialize())
            messages.success(request, _('The API token has been upgraded.'))
        elif token_id := request.POST.get('revoke'):
            with scopes_disabled():
                token = request.user.api_tokens.filter(pk=token_id).first()
                if token:
                    token.expires = now()
                    token.save()
                    request.user.log_action('eventyay.user.token.revoke', data=token.serialize())
                    messages.success(request, _('The API token was revoked.'))
        else:
            messages.error(self.request, phrases.base.error_saving_changes)
            return self.get(request, *args, **kwargs)
        return redirect(self.get_success_url())

    @context
    @cached_property
    def tokens(self):
        with scopes_disabled():
            return self.request.user.api_tokens.all().order_by('-expires')


class SubuserView(View):
    def dispatch(self, request, *args, **kwargs):
        request.user.is_administrator = request.user.is_superuser
        request.user.is_superuser = False
        request.user.save(update_fields=['is_administrator', 'is_superuser'])
        messages.success(request, _('You are now an administrator instead of a superuser.'))
        params = request.GET.copy()
        url = urllib.parse.unquote(params.pop('next', [''])[0])
        if url and url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            return redirect(url + ('?' + params.urlencode() if params else ''))
        return redirect(reverse('orga:event.list'))
