from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from pretalx.event.models import Event
from pretalx.orga.views.event import EventSettingsPermission

from .forms import VenuelessSettingsForm
from .venueless import push_to_venueless


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
        return kwargs

    def get_context_data(self):
        data = super().get_context_data()
        data["connect_in_progress"] = self.request.GET.get("token")
        data["last_push"] = self.request.event.settings.venueless_last_push
        return data

    def form_valid(self, form):
        form.save()

        # TODO use short token / login URL to get long token
        # then save the long token and perform the POST request below

        try:
            push_to_venueless(self.request.event)
            redirect_url = self.request.GET.get("returnUrl")
            if redirect_url:
                return redirect(redirect_url)
            messages.success(self.request, _("Yay! We saved your changes."))
        except Exception as e:
            messages.error(self.request, _("Unable to reach Venueless:") + f" {e}")
        return super().form_valid(form)


def check(request, event):
    e = Event.objects.filter(slug__iexact=event).first()
    response = HttpResponse("")
    if not e or "pretalx_venueless" not in e.plugin_list:
        response.status_code = 404
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response
