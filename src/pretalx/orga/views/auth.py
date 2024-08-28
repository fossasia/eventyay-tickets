import datetime as dt

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.views.generic import FormView

from pretalx.cfp.forms.auth import RecoverForm, ResetForm
from pretalx.common.text.phrases import phrases
from pretalx.common.views import GenericLoginView, GenericResetView
from pretalx.person.models import User


class LoginView(GenericLoginView):
    template_name = "orga/auth/login.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site_name"] = dict(settings.CONFIG.items("site")).get("name")
        return context

    @cached_property
    def event(self):
        return getattr(self.request, "event", None)

    @property
    def success_url(self):
        if self.event:
            return self.event.orga_urls.base
        return reverse("orga:event.list")

    def get_password_reset_link(self):
        if self.event:
            return reverse("orga:event.auth.reset", kwargs={"event": self.event.slug})
        return reverse("orga:auth.reset")


def logout_view(request):
    logout(request)
    return redirect(
        GenericLoginView.get_next_url_or_fallback(request, reverse("orga:login"))
    )


class ResetView(GenericResetView):
    template_name = "orga/auth/reset.html"
    form_class = ResetForm

    def get_success_url(self):
        return reverse("orga:login")


class RecoverView(FormView):
    template_name = "orga/auth/recover.html"
    form_class = RecoverForm

    def __init__(self, **kwargs):
        self.user = None
        super().__init__(**kwargs)

    def get_user(self):
        return User.objects.get(
            pw_reset_token=self.kwargs.get("token"),
            pw_reset_time__gte=now() - dt.timedelta(days=1),
        )

    def dispatch(self, request, *args, **kwargs):
        try:
            self.get_user()
        except User.DoesNotExist:
            messages.error(self.request, phrases.cfp.auth_reset_fail)
            return redirect(reverse("orga:auth.reset"))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = self.get_user()
        user.set_password(form.cleaned_data["password"])
        user.pw_reset_token = None
        user.pw_reset_time = None
        user.save()
        messages.success(self.request, phrases.cfp.auth_reset_success)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("orga:login")
