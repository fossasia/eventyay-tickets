from datetime import timedelta
from importlib import import_module

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, View

from pretalx.cfp.forms.auth import RecoverForm
from pretalx.cfp.views.event import EventPageMixin
from pretalx.common.phrases import phrases
from pretalx.common.views import GenericLoginView, GenericResetView
from pretalx.person.models import User

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


class LogoutView(View):
    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponseRedirect:
        logout(request)
        return redirect(
            reverse('cfp:event.start', kwargs={'event': self.request.event.slug})
        )


class LoginView(GenericLoginView):
    template_name = 'cfp/event/login.html'

    def get_error_url(self):
        return self.request.event.urls.base

    def get_success_url(self):
        return self.request.event.urls.user_submissions

    def get_password_reset_link(self):
        return self.request.event.urls.reset


class ResetView(EventPageMixin, GenericResetView):
    template_name = 'cfp/event/reset.html'

    def get_success_url(self):
        return reverse('cfp:event.login', kwargs={'event': self.request.event.slug})


class RecoverView(FormView):
    template_name = 'cfp/event/recover.html'
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
            return redirect(
                reverse('cfp:event.reset', kwargs={'event': kwargs.get('event')})
            )

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.user.set_password(form.cleaned_data['password'])
        self.user.pw_reset_token = None
        self.user.pw_reset_time = None
        self.user.save()
        messages.success(self.request, phrases.cfp.auth_reset_success)
        return redirect(
            reverse('cfp:event.login', kwargs={'event': self.request.event.slug})
        )


class EventAuth(View):
    """
    Taken from pretix' brilliant solution for multidomain auth.
    """

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def post(request, *args, **kwargs):
        store = SessionStore(request.POST.get('session'))

        try:
            data = store.load()
        except Exception:
            raise PermissionDenied(_('Please go back and try again.'))

        key = f'pretalx_event_access_{request.event.pk}'
        parent = data.get(key)
        sparent = SessionStore(parent)

        try:
            parentdata = sparent.load()
        except Exception:
            raise PermissionDenied(_('Please go back and try again.'))
        else:
            if 'event_access' not in parentdata:
                raise PermissionDenied(_('Please go back and try again.'))

        request.session[key] = parent
        url = request.event.urls.base
        if 'target' in request.POST:
            if request.POST['target'] == 'cfp':
                url = request.event.cfp.urls.public
            elif request.POST['target'] == 'schedule':
                url = request.event.urls.schedule
        return redirect(url)
