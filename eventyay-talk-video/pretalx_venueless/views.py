import datetime as dt

import jwt
from csp.decorators import csp_replace
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
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
        kwargs["event"] = self.request.event
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


@method_decorator(xframe_options_exempt, "dispatch")
class SpeakerJoin(View):
    def post(self, request, *args, **kwargs):
        speaker = request.user
        if speaker.is_anonymous:
            raise Http404(_("Unknown user or not authorized to access venueless."))
        if speaker not in request.event.speakers:
            raise PermissionDenied()

        venueless_settings = request.event.venueless_settings
        if venueless_settings.join_start and venueless_settings.join_start < now():
            raise PermissionDenied()

        talks = request.event.talks.filter(speakers__in=[speaker]).distinct()
        iat = dt.datetime.utcnow()
        exp = iat + dt.timedelta(days=30)
        profile = {
            "display_name": speaker.name,
            "fields": {
                "pretalx_id": speaker.code,
            },
        }
        if speaker.avatar_url:
            profile["profile_picture"] = speaker.get_avatar_url(request.event)

        payload = {
            "iss": venueless_settings.issuer,
            "aud": venueless_settings.audience,
            "exp": exp,
            "iat": iat,
            "uid": speaker.code,
            "profile": profile,
            "traits": list(
                {
                    f"eventyay-video-event-{request.event.slug}",
                }
                | {f"eventyay-video-session-{submission.code}" for submission in talks}
            ),
        }
        token = jwt.encode(payload, venueless_settings.secret, algorithm="HS256")
        speaker.profiles.filter(event=request.event).update(has_arrived=True)

        return redirect(
            "{}/#token={}".format(venueless_settings.join_url, token).replace(
                "//#", "/#"
            )
        )
