from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils.timezone import now
from django.views.generic import TemplateView
from django_context_decorator import context

from pretalx.common.mixins.views import PermissionRequired
from pretalx.event.models import Event


class EventPageMixin(PermissionRequired):
    permission_required = 'cfp.view_event'

    def get_permission_object(self):
        return getattr(self.request, 'event', None)


# check login first, then permission so users get redirected to /login, if they are missing one
class LoggedInEventPageMixin(LoginRequiredMixin, EventPageMixin):
    def get_login_url(self) -> str:
        return reverse('cfp:event.login', kwargs={'event': self.request.event.slug})


class EventStartpage(EventPageMixin, TemplateView):
    template_name = 'cfp/event/index.html'

    @context
    def has_submissions(self):
        return (
            not self.request.user.is_anonymous
            and self.request.event.submissions.filter(
                speakers__in=[self.request.user]
            ).exists()
        )

    @context
    def has_sneak_peek(self):
        return self.request.event.submissions.filter(is_featured=True).exists()

    @context
    def submit_qs(self):
        params = [
            (key, self.request.GET.get(key))
            for key in ['track', 'submission_type']
            if self.request.GET.get(key) is not None
        ]
        return f'?{urlencode(params)}' if params else ''


class EventCfP(EventStartpage):
    template_name = 'cfp/event/cfp.html'


class GeneralView(TemplateView):
    template_name = 'cfp/index.html'

    def filter_events(self, events):
        if self.request.user.is_anonymous:
            return [
                e for e in events.filter(is_public=True) if e.settings.show_on_dashboard
            ]
        return [
            e
            for e in events
            if (e.is_public and e.settings.show_on_dashboard)
            or self.request.user.has_perm('cfp.view_event', e)
        ]

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        _now = now().date()
        qs = Event.objects.order_by('-date_to')
        result['current_events'] = self.filter_events(
            qs.filter(date_from__lte=_now, date_to__gte=_now)
        )
        result['past_events'] = self.filter_events(qs.filter(date_to__lt=_now))
        result['future_events'] = self.filter_events(qs.filter(date_from__gt=_now))
        return result
