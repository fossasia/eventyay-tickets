from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.views.generic import FormView

from pretalx.cfp.forms.auth import RecoverForm, ResetForm
from pretalx.common.phrases import phrases
from pretalx.common.views import GenericLoginView, GenericResetView
from pretalx.person.models import User


class LoginView(GenericLoginView):
    template_name = 'orga/auth/login.html'

    @cached_property
    def event(self):
        return getattr(self.request, 'event', None)

    def get_error_url(self):
        if self.event:
            return reverse('orga:event.login', kwargs={'event': self.event.slug})
        return reverse('orga:login')

    def get_success_url(self):
        messages.success(self.request, phrases.orga.logged_in)
        if self.event:
            return self.event.orga_urls.base
        return reverse('orga:event.list')

    def get_password_reset_link(self):
        if self.event:
            return reverse('orga:event.auth.reset', kwargs={'event': self.event.slug})
        return reverse('orga:auth.reset')


def logout_view(request: HttpRequest) -> HttpResponseRedirect:
    logout(request)
    return redirect(reverse('orga:login'))


class ResetView(GenericResetView):
    template_name = 'orga/auth/reset.html'
    form_class = ResetForm

    def get_success_url(self):
        return reverse('orga:login')


class RecoverView(FormView):
    template_name = 'orga/auth/recover.html'
    form_class = RecoverForm

    def __init__(self, **kwargs):
        self.user = None
        super().__init__(**kwargs)

    def dispatch(self, request, *args, **kwargs):
        try:
            self.user = User.objects.get(
                pw_reset_token=kwargs.get('token'),
                pw_reset_time__gte=now() - timedelta(days=1),
            )
        except User.DoesNotExist:
            messages.error(self.request, phrases.cfp.auth_reset_fail)
            return redirect(reverse('orga:auth.reset'))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.user.set_password(form.cleaned_data['password'])
        self.user.pw_reset_token = None
        self.user.pw_reset_time = None
        self.user.save()
        messages.success(self.request, phrases.cfp.auth_reset_success)
        return redirect(reverse('orga:login'))
