import urllib
from contextlib import suppress

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import FileResponse, Http404, HttpResponseServerError
from django.shortcuts import redirect
from django.template import TemplateDoesNotExist, loader
from django.urls import get_callable
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now
from django.views.generic import FormView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView
from django_context_decorator import context

from pretalx.cfp.forms.auth import ResetForm
from pretalx.common.exceptions import SendMailException
from pretalx.common.phrases import phrases
from pretalx.person.forms import UserForm
from pretalx.person.models import User


class CreateOrUpdateView(
    SingleObjectTemplateResponseMixin, ModelFormMixin, ProcessFormView
):
    def set_object(self):
        if getattr(self, "object", None) is None:
            setattr(self, "object", None)
        with suppress(self.model.DoesNotExist, AttributeError):
            setattr(self, "object", self.get_object())

    def get(self, request, *args, **kwargs):
        self.set_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.set_object()
        return super().post(request, *args, **kwargs)


def is_form_bound(request, form_name, form_param="form"):
    return request.method == "POST" and request.POST.get(form_param) == form_name


def get_static(request, path, content_type):  # pragma: no cover
    """TODO: move to staticfiles usage as per https://gist.github.com/SmileyChris/8d472f2a67526e36f39f3c33520182bc
    This would avoid potential directory traversal by … a malicious urlconfig, so not a huge attack vector."""
    path = settings.BASE_DIR / "pretalx/static" / path
    if not path.exists():
        raise Http404()
    return FileResponse(
        open(path, "rb"), content_type=content_type, as_attachment=False
    )


class GenericLoginView(FormView):
    form_class = UserForm

    @context
    def password_reset_link(self):
        return self.get_password_reset_link()

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_anonymous:
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    @classmethod
    def get_next_url_or_fallback(cls, request, fallback):
        """Reused in logout()"""
        params = request.GET.copy()
        url = urllib.parse.unquote(params.pop("next", [""])[0])
        params = "?" + params.urlencode() if params else ""
        if url and url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            return url + params
        return fallback + params

    def get_success_url(self):
        return self.get_next_url_or_fallback(self.request, self.success_url)

    def form_valid(self, form):
        pk = form.save()
        user = User.objects.filter(pk=pk).first()
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect(self.get_success_url())


class GenericResetView(FormView):
    form_class = ResetForm

    def form_valid(self, form):
        user = form.cleaned_data["user"]

        if not user or (
            user.pw_reset_time
            and (now() - user.pw_reset_time).total_seconds() < 3600 * 24
        ):
            messages.success(self.request, phrases.cfp.auth_password_reset)
            return redirect(self.get_success_url())

        try:
            user.reset_password(
                event=getattr(self.request, "event", None),
                orga="orga" in self.request.resolver_match.namespaces,
            )
        except SendMailException:  # pragma: no cover
            messages.error(self.request, phrases.base.error_sending_mail)
            return self.get(self.request, *self.args, **self.kwargs)

        messages.success(self.request, phrases.cfp.auth_password_reset)
        user.log_action("pretalx.user.password.reset")

        return redirect(self.get_success_url())


def handle_500(request):
    try:
        template = loader.get_template("500.html")
    except TemplateDoesNotExist:  # pragma: no cover
        return HttpResponseServerError(
            "Internal server error. Please contact the administrator for details.",
            content_type="text/html",
        )
    context = {}
    try:  # This should never fail, but can't be too cautious in error views
        context["request_path"] = urllib.parse.quote(request.path)
    except Exception:  # pragma: no cover
        pass
    return HttpResponseServerError(template.render(context))


def error_view(status_code):
    if status_code == 4031:
        return get_callable(settings.CSRF_FAILURE_VIEW)
    if status_code == 500:
        return handle_500
    exceptions = {
        400: SuspiciousOperation,
        403: PermissionDenied,
        404: Http404,
    }
    exception = exceptions[status_code]

    def error_view(request, *args, **kwargs):
        raise exception

    return error_view
