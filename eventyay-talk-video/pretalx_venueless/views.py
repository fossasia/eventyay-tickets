from csp.decorators import csp_replace
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from pretalx.event.models import Event
from pretalx.orga.views.event import EventSettingsPermission

from .forms import VenuelessSettingsForm
from .venueless import push_to_venueless


@method_decorator(csp_replace(FORM_ACTION="*"), name="dispatch")
class Settings(EventSettingsPermission, FormView):
    form_class = VenuelessSettingsForm
    template_name = "pretalx_venueless/settings.html"

    def get_success_url(self) -> str:
        return reverse(
            "plugins:pretalx_venueless:settings",
            kwargs={
                "event": self.request.event.slug,
            },
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["obj"] = self.request.event
        kwargs["attribute_name"] = "settings"
        if "token" in self.request.GET:
            kwargs["initial_token"] = self.request.GET.get("token")
        if "url" in self.request.GET:
            kwargs["initial_url"] = self.request.GET.get("url")
        if "returnUrl" in self.request.GET:
            kwargs["return_url"] = self.request.GET.get("returnUrl")
        return kwargs

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data["connect_in_progress"] = self.request.GET.get("token")
        data["last_push"] = self.request.event.settings.venueless_last_push
        return data

    def form_valid(self, form):
        form.save()

        # TODO use short token / login URL to get long token
        # then save the long token and perform the POST request below

        response = None
        try:
            response = push_to_venueless(self.request.event)
            response.raise_for_status()
            redirect_url = form.cleaned_data.get("return_url")
            if redirect_url:
                return redirect(redirect_url)
            messages.success(self.request, _("Yay! We saved your changes."))
        except Exception as e:
            error_message = ""
            if response is not None and len(response.content.decode()) < 100:
                error_message = response.content.decode().strip('"')
            if not error_message:
                error_message = str(e)
            messages.error(
                self.request, _("Unable to reach Venueless:") + f" {error_message}"
            )
        return super().form_valid(form)


def check(request, event):
    e = Event.objects.filter(slug__iexact=event).first()
    response = HttpResponse("")
    if not e or "pretalx_venueless" not in e.plugin_list:
        response.status_code = 404
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response
