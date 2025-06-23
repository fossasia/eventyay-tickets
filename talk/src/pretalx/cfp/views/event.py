from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils.timezone import now
from django.views.generic import TemplateView
from django_context_decorator import context

from pretalx.common.views.mixins import PermissionRequired
from pretalx.event.models import Event


class EventPageMixin(PermissionRequired):
    permission_required = "cfp.view_event"

    def get_permission_object(self):
        return getattr(self.request, "event", None)


# check login first, then permission so users get redirected to /login, if they are missing one
class LoggedInEventPageMixin(LoginRequiredMixin, EventPageMixin):
    def get_login_url(self) -> str:
        return reverse("cfp:event.login", kwargs={"event": self.request.event.slug})


class EventStartpage(EventPageMixin, TemplateView):
    template_name = "cfp/event/index.html"

    @context
    def has_submissions(self):
        return (
            not self.request.user.is_anonymous
            and self.request.event.submissions.filter(
                speakers__in=[self.request.user]
            ).exists()
        )

    @context
    def has_featured(self):
        return self.request.event.submissions.filter(is_featured=True).exists()

    @context
    def submit_qs(self):
        params = [
            (key, self.request.GET.get(key))
            for key in ("track", "submission_type", "access_code")
            if self.request.GET.get(key) is not None
        ]
        return f"?{urlencode(params)}" if params else ""

    @context
    def access_code(self):
        code = self.request.GET.get("access_code")
        if code:
            return self.request.event.submitter_access_codes.filter(
                code__iexact=code
            ).first()


class EventCfP(EventStartpage):
    template_name = "cfp/event/cfp.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site_name = dict(settings.CONFIG.items("site")).get("name")
        context["site_name"] = site_name
        return context

    @context
    def has_featured(self):
        return self.request.event.submissions.filter(is_featured=True).exists()


class GeneralView(TemplateView):
    template_name = "cfp/index.html"

    def filter_events(self, events):
        if self.request.user.is_anonymous:
            events.filter(is_public=True)
        return [
            event
            for event in events
            if event.is_public or self.request.user.has_perm("cfp.view_event", event)
        ]

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        _now = now().date()
        qs = Event.objects.order_by("-date_to")
        if self.request.uses_custom_domain:
            qs = qs.filter(custom_domain=f"https://{self.request.host}")
        else:
            qs = qs.filter(custom_domain__isnull=True)
        result["current_events"] = self.filter_events(
            qs.filter(date_from__lte=_now, date_to__gte=_now)
        )
        result["past_events"] = self.filter_events(qs.filter(date_to__lt=_now))
        result["future_events"] = self.filter_events(qs.filter(date_from__gt=_now))
        return result
