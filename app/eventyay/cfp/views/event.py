from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils.timezone import now
from django.views.generic import TemplateView
from django_context_decorator import context

from eventyay.common.views.mixins import PermissionRequired
from eventyay.base.models import Event
from eventyay.talk_rules.event import get_events_for_user


class EventPageMixin(PermissionRequired):
    permission_required = 'base.view_event'

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
            and self.request.event.submissions.filter(speakers__in=[self.request.user]).exists()
        )

    @context
    def has_featured(self):
        return self.request.event.submissions.filter(is_featured=True).exists()

    @context
    def submit_qs(self):
        params = [
            (key, self.request.GET.get(key))
            for key in ('track', 'submission_type', 'access_code')
            if self.request.GET.get(key) is not None
        ]
        return f'?{urlencode(params)}' if params else ''

    @context
    def access_code(self):
        code = self.request.GET.get('access_code')
        if code:
            return self.request.event.submitter_access_codes.filter(code__iexact=code).first()


class EventCfP(EventStartpage):
    template_name = 'cfp/event/cfp.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site_name = dict(settings.TALK_CONFIG.items('site')).get('name')
        context['site_name'] = site_name
        return context

    @context
    def has_featured(self):
        return self.request.event.submissions.filter(is_featured=True).exists()


class GeneralView(TemplateView):
    template_name = 'cfp/index.html'

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        _now = now().date()
        if self.request.uses_custom_domain:
            qs = Event.objects.filter(custom_domain=f'https://{self.request.host}')
        else:
            qs = Event.objects.filter(custom_domain__isnull=True)
        qs = get_events_for_user(self.request.user, qs)
        result['current_events'] = []
        result['past_events'] = []
        result['future_events'] = []
        for event in qs:
            if event.date_from.date() <= _now <= event.date_to.date():
                result['current_events'].append(event)
            elif event.date_to.date() < _now:
                result['past_events'].append(event)
            else:
                result['future_events'].append(event)
        return result
