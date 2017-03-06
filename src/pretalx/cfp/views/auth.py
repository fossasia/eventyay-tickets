from django.contrib.auth import logout, login
from django.core.urlresolvers import reverse
from django.http import HttpRequest
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.utils.http import is_safe_url
from django.views.generic import View, FormView

from pretalx.cfp.forms.auth import LoginForm
from pretalx.cfp.views.event import EventPageMixin


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
