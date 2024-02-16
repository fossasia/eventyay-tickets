import urllib
from contextlib import suppress

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import FileResponse, Http404, HttpResponseServerError
from django.shortcuts import get_object_or_404, redirect
from django.template import TemplateDoesNotExist, loader
from django.urls import NoReverseMatch, get_callable, path
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from django.views.generic import FormView, View
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView
from django_context_decorator import context

from pretalx.cfp.forms.auth import ResetForm
from pretalx.common.exceptions import SendMailException
from pretalx.common.mixins.views import SocialMediaCardMixin
from pretalx.common.phrases import phrases
from pretalx.person.forms import UserForm
from pretalx.person.models import User


class CreateOrUpdateView(
    SingleObjectTemplateResponseMixin, ModelFormMixin, ProcessFormView
):
    def set_object(self):
        with suppress(self.model.DoesNotExist, AttributeError):
            self.object = self.get_object()

    def get(self, request, *args, **kwargs):
        self.set_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.set_object()
        return super().post(request, *args, **kwargs)


def is_form_bound(request, form_name, form_param="form"):
    return request.method == "POST" and request.POST.get(form_param) == form_name


def get_static(request, path, content_type):  # pragma: no cover
    path = settings.BASE_DIR / "pretalx/static" / path
    if not path.exists():
        raise Http404()
    return FileResponse(
        open(path, "rb"), content_type=content_type, as_attachment=False
    )


class EventSocialMediaCard(SocialMediaCardMixin, View):
    pass


class GenericLoginView(FormView):
    form_class = UserForm

    @context
    def password_reset_link(self):
        return self.get_password_reset_link()

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_anonymous:
            try:
                return redirect(self.get_success_url())
            except Exception:
                return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    @classmethod
    def get_next_url_or_fallback(cls, request, fallback, ignore_next=False):
        """Reused in logout()"""
        params = request.GET.copy()
        url = None if ignore_next else urllib.parse.unquote(params.pop("next", [""])[0])
        params = "?" + params.urlencode() if params else ""
        if url and url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            return url + params
        return fallback + params

    def get_success_url(self, ignore_next=False):
        return self.get_next_url_or_fallback(
            self.request, self.success_url, ignore_next=ignore_next
        )

    def get_redirect(self):
        try:
            return redirect(self.get_success_url())
        except NoReverseMatch:
            return redirect(self.get_success_url(ignore_next=True))

    def form_valid(self, form):
        pk = form.save()
        user = User.objects.filter(pk=pk).first()
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        return self.get_redirect()


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


def conditional_cache_page(
    timeout, condition, *, cache=None, key_prefix=None, cache_control=None
):
    """This decorator is exactly like cache_page, but with the option to skip
    the caching entirely.

    The second argument is a callable, ``condition``. It's given the
    request and all further arguments, and if it evaluates to a true-ish
    value, the cache is used.
    """

    def decorator(func):
        def wrapper(request, *args, **kwargs):
            if condition(request, *args, **kwargs):
                prefix = key_prefix
                if callable(prefix):
                    prefix = prefix(request, *args, **kwargs)
                response = cache_page(timeout=timeout, cache=cache, key_prefix=prefix)(
                    func
                )(request, *args, **kwargs)
                if cache_control and not cache_control(request, *args, **kwargs):
                    response.headers.pop("Expires")
                    response.headers.pop("Cache-Control")

            return func(request, *args, **kwargs)

        return wrapper

    return decorator


class OrderModelView(View):
    """
    Use with OrderedModels to provide up and down links in the list view.

    You need to implement/override
    - model
    - permission_required
    - get_success_url

    In urls.py, use MyOrderModelView.get_urls() to get the urls for this view.
    """

    model = None
    permission_required = None
    direction_up = True

    def __init__(self, *args, direction_up=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.direction_up = direction_up

    def get_queryset(self):
        return self.model.get_order_queryset(event=self.request.event)

    def dispatch(self, request, *args, direction=None, pk=None, **kwargs):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        if not request.user.has_perm(self.permission_required, obj):
            messages.error(
                request, _("Sorry, you are not allowed to reorder this list.")
            )
            raise Http404()
        obj.move(up=self.direction_up)
        messages.success(request, _("The order has been updated."))
        return redirect(self.get_success_url())

    def get_success_url(self):
        return self.request.event.orga_urls.base

    @classmethod
    def get_urls(cls, base_url=""):
        # Return the two patterns for moving up and down
        url_name = f"settings.{cls.model._meta.app_label}.{cls.model._meta.model_name}."
        return [
            path(
                f"{base_url}up",
                cls.as_view(direction_up=True),
                name=f"{url_name}.up",
            ),
            path(
                f"{base_url}down",
                cls.as_view(direction_up=False),
                name=f"{url_name}.down",
            ),
        ]
