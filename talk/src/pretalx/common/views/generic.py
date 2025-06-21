import datetime as dt
import urllib
from contextlib import suppress

from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect
from django.urls import NoReverseMatch
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now
from django.views.generic import FormView, View
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView
from django_context_decorator import context

from pretalx.cfp.forms.auth import ResetForm
from pretalx.common.exceptions import SendMailException
from pretalx.common.text.phrases import phrases
from pretalx.common.views.mixins import SocialMediaCardMixin
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
        one_day_ago = now() - dt.timedelta(hours=24)

        # We block password resets if the user has reset their password already in the
        # past 24 hours.
        # We permit the reset if the password reset time is in the future, as this can
        # only be due to the way we handle speaker invitations at the moment.
        if not user or (
            user.pw_reset_time and (one_day_ago < user.pw_reset_time < now())
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


class EventSocialMediaCard(SocialMediaCardMixin, View):
    pass
