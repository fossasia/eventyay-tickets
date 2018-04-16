from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import TemplateView

from pretalx.common.mixins.views import PermissionRequired
from pretalx.event.models import Event


class EventPageMixin(PermissionRequired):
    permission_required = 'cfp.view_event'

    def get_permission_object(self):
        return getattr(self.request, 'event', None)


class LoggedInEventPageMixin(EventPageMixin, LoginRequiredMixin):

    def get_login_url(self) -> str:
        return reverse('cfp:event.login', kwargs={
            'event': self.request.event.slug
        })


class EventStartpage(EventPageMixin, TemplateView):
    template_name = 'cfp/event/index.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['has_submissions'] = not self.request.user.is_anonymous and self.request.event.submissions.filter(speakers__in=[self.request.user]).exists()
        return context


class EventCfP(EventStartpage):
    template_name = 'cfp/event/cfp.html'


class GeneralView(TemplateView):
    template_name = 'cfp/index.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['events'] = Event.objects.filter(is_public=True)
        context['orga_events'] = [e for e in Event.objects.filter(is_public=False) if self.request.user.has_perm('cfp.view_event', e)]
        return context
