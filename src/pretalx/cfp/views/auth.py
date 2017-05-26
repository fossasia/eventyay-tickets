from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.http import is_safe_url
from django.utils.timezone import now
from django.utils.translation import get_language, ugettext_lazy as _
from django.views.generic import FormView, View

from pretalx.cfp.forms.auth import LoginForm, RecoverForm, ResetForm
from pretalx.cfp.views.event import EventPageMixin
from pretalx.common.mail import SendMailException, mail
from pretalx.common.urls import build_absolute_uri
from pretalx.person.models import User


class LogoutView(EventPageMixin, View):
    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponseRedirect:
        logout(request)
        return redirect(reverse('cfp:event.start', kwargs={
            'event': self.request.event.slug
        }))


class LoginView(EventPageMixin, FormView):
    template_name = 'cfp/event/login.html'
    form_class = LoginForm

    def form_valid(self, form):
        login(self.request, form.cleaned_data['user'])

        url = self.request.GET.get('next')
        if url and is_safe_url(url, self.request.get_host()):
            return redirect(url)

        return redirect(reverse('cfp:event.user.submissions', kwargs={
            'event': self.request.event.slug
        }))


class ResetView(EventPageMixin, FormView):
    template_name = 'cfp/event/reset.html'
    form_class = ResetForm

    def form_valid(self, form):
        user = form.cleaned_data['user']

        if user.pw_reset_time and (now() - user.pw_reset_time).total_seconds() < 3600 * 24:
            messages.error(self.request, _('You already requested a new password within the last 24 hours.'))
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
                        'cfp:event.recover', kwargs={
                            'event': self.request.event.slug,
                            'token': user.pw_reset_token,
                        }
                    )
                },
                self.request.event,
                locale=get_language()
            )
        except SendMailException:
            messages.error(self.request, _('There was an error sending the mail. Please try again later.'))
            return self.get(self.request, *self.args, **self.kwargs)

        messages.success(self.request, _('We will send you an e-mail containing further instructions. If you don\'t '
                                         'see the email within the next minutes, check your spam inbox!'))
        user.log_action('pretalx.user.password_reset', person=user)

        return redirect(reverse('cfp:event.login', kwargs={
            'event': self.request.event.slug
        }))


class RecoverView(EventPageMixin, FormView):
    template_name = 'cfp/event/recover.html'
    form_class = RecoverForm

    def dispatch(self, request, *args, **kwargs):
        try:
            self.user = User.objects.get(
                pw_reset_token=kwargs.get('token'),
                pw_reset_time__gte=now() - timedelta(days=1)
            )
        except User.DoesNotExist:
            messages.error(self.request, _('This link was not valid. Make sure you copied the complete URL from the '
                                           'email and that the email is no more than 24 hours old.'))
            return redirect(reverse('cfp:event.reset', kwargs={
                'event': kwargs.get('event')
            }))

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.user.set_password(form.cleaned_data['password'])
        self.user.pw_reset_token = None
        self.user.pw_reset_time = None
        self.user.save()
        messages.success(self.request, _('Awesome! You can now log in using your new password.'))
        return redirect(reverse('cfp:event.login', kwargs={
            'event': self.request.event.slug
        }))
