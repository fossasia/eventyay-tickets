import urllib
from contextlib import suppress

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.utils.http import is_safe_url
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView
from django_context_decorator import context

from pretalx.cfp.forms.auth import ResetForm
from pretalx.common.mail import SendMailException
from pretalx.common.phrases import phrases
from pretalx.person.forms import UserForm
from pretalx.person.models import User


class CreateOrUpdateView(
    SingleObjectTemplateResponseMixin, ModelFormMixin, ProcessFormView
):
    def set_object(self):
        if getattr(self, 'object', None) is None:
            setattr(self, 'object', None)
        with suppress(self.model.DoesNotExist, AttributeError):
            setattr(self, 'object', self.get_object())

    def get(self, request, *args, **kwargs):
        self.set_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.set_object()
        return super().post(request, *args, **kwargs)


def is_form_bound(request, form_name, form_param='form'):
    return request.method == 'POST' and request.POST.get(form_param) == form_name


def get_static(request, path, content_type):
    """TODO: move to staticfiles usage as per https://gist.github.com/SmileyChris/8d472f2a67526e36f39f3c33520182bc
    This would avoid potential directory traversal by … a malicious urlconfig, so not a huge attack vector."""
    path = settings.BASE_DIR / 'pretalx/static' / path
    if not path.exists():
        raise Http404()
    return FileResponse(open(path, 'rb'), content_type=content_type, as_attachment=False)


class GenericLoginView(FormView):
    form_class = UserForm

    @context
    def password_reset_link(self):
        return self.get_password_reset_link()

    def form_valid(self, form):
        pk = form.save()
        user = User.objects.filter(pk=pk).first()
        if not user:
            messages.error(
                self.request,
                _(
                    'There was an error when logging in. Please contact the organiser for further help.'
                ),
            )
            return redirect(self.get_error_url())
        if not user.is_active:
            messages.error(self.request, _('User account is deactivated.'))
            return redirect(self.get_error_redirect())

        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')

        params = self.request.GET.copy()
        url = urllib.parse.unquote(params.pop('next', [''])[0])
        if url and is_safe_url(url, allowed_hosts=None):
            return redirect(url + ('?' + params.urlencode() if params else ''))

        return redirect(self.get_success_url())


class GenericResetView(FormView):
    form_class = ResetForm

    def form_valid(self, form):
        user = form.cleaned_data['user']

        if not user or (
            user.pw_reset_time
            and (now() - user.pw_reset_time).total_seconds() < 3600 * 24
        ):
            messages.success(self.request, phrases.cfp.auth_password_reset)
            return redirect(self.get_success_url())

        try:
            user.reset_password(event=getattr(self.request, 'event', None))
        except SendMailException:
            messages.error(self.request, phrases.base.error_sending_mail)
            return self.get(self.request, *self.args, **self.kwargs)

        messages.success(self.request, phrases.cfp.auth_password_reset)
        user.log_action('pretalx.user.password.reset')

        return redirect(self.get_success_url())
