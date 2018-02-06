from datetime import timedelta

from csp.decorators import csp_update
from django.contrib import messages
from django.contrib.auth import login, logout
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.utils.http import is_safe_url
from django.utils.timezone import now
from django.utils.translation import get_language, ugettext_lazy as _
from django.views.generic import FormView, View

from pretalx.cfp.forms.auth import RecoverForm, ResetForm
from pretalx.cfp.views.event import EventPageMixin
from pretalx.common.mail import SendMailException, mail
from pretalx.common.phrases import phrases
from pretalx.common.urls import build_absolute_uri
from pretalx.person.forms import UserForm
from pretalx.person.models import User


class LogoutView(View):
    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponseRedirect:
        logout(request)
        return redirect(reverse('cfp:event.start', kwargs={
            'event': self.request.event.slug
        }))


@method_decorator(csp_update(SCRIPT_SRC="'self' 'unsafe-inline'"), name='dispatch')
class LoginView(FormView):
    template_name = 'cfp/event/login.html'
    form_class = UserForm

    def form_valid(self, form):
        pk = form.save()
        user = User.objects.filter(pk=pk).first()
        if not user:
            messages.error(self.request, _('There was an error when logging in. Please contact the organiser for further help.'))
            return redirect(self.request.event.urls.base)

        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')

        url = self.request.GET.get('next')
        if url and is_safe_url(url, self.request.get_host()):
            return redirect(url)

        return redirect(self.request.event.urls.user_submissions)


class ResetView(EventPageMixin, FormView):
    template_name = 'cfp/event/reset.html'
    form_class = ResetForm

    def form_valid(self, form):
        user = form.cleaned_data['user']

        if not user:
            messages.success(self.request, phrases.cfp.auth_password_reset)
            return redirect(reverse('cfp:event.login', kwargs={
                'event': self.request.event.slug
            }))

        if user.pw_reset_time and (now() - user.pw_reset_time).total_seconds() < 3600 * 24:
            messages.error(self.request, phrases.cfp.auth_already_requested)
            return redirect(reverse('cfp:event.reset', kwargs={
                'event': self.request.event.slug
            }))

        try:
            user.pw_reset_token = get_random_string(32)
            user.pw_reset_time = now()
            user.save()
            mail(
                user,
                _('Password recovery'),
                self.request.event.settings.mail_text_reset,
                {
                    'name': user.name or user.nick,
                    'event': self.request.event.name,
                    'url': build_absolute_uri(
                        'cfp:event.recover', event=self.request.event, kwargs={
                            'event': self.request.event.slug,
                            'token': user.pw_reset_token,
                        }
                    )
                },
                self.request.event,
                locale=get_language()
            )
        except SendMailException:
            messages.error(self.request, phrases.base.error_sending_mail)
            return self.get(self.request, *self.args, **self.kwargs)

        messages.success(self.request, phrases.cfp.auth_password_reset)
        user.log_action('pretalx.user.password.reset')

        return redirect(reverse('cfp:event.login', kwargs={
            'event': self.request.event.slug
        }))


@method_decorator(csp_update(SCRIPT_SRC="'self' 'unsafe-inline'"), name='dispatch')
class RecoverView(FormView):
    template_name = 'cfp/event/recover.html'
    form_class = RecoverForm

    def dispatch(self, request, *args, **kwargs):
        try:
            self.user = User.objects.get(
                pw_reset_token=kwargs.get('token'),
                pw_reset_time__gte=now() - timedelta(days=1)
            )
        except User.DoesNotExist:
            messages.error(self.request, phrases.cfp.auth_reset_fail)
            return redirect(reverse('cfp:event.reset', kwargs={
                'event': kwargs.get('event')
            }))

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.user.set_password(form.cleaned_data['password'])
        self.user.pw_reset_token = None
        self.user.pw_reset_time = None
        self.user.save()
        messages.success(self.request, phrases.cfp.auth_reset_success)
        return redirect(reverse('cfp:event.login', kwargs={
            'event': self.request.event.slug
        }))
