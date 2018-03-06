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


class EventCfP(EventPageMixin, TemplateView):
    template_name = 'cfp/event/cfp.html'


class GeneralView(TemplateView):
    template_name = 'cfp/index.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['events'] = Event.objects.filter(is_public=True)
        ctx['orga_events'] = [e for e in Event.objects.filter(is_public=False) if self.request.user.has_perm('cfp.view_event', e)]
        return ctx
