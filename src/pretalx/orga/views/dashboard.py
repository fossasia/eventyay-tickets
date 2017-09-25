from django.views.generic import TemplateView

from pretalx.event.stages import get_stages


class DashboardView(TemplateView):
    template_name = 'orga/dashboard.html'


class EventDashboardView(TemplateView):
    template_name = 'orga/event/dashboard.html'

    def get_context_data(self, event):
        ctx = super().get_context_data()
        event = self.request.event
        ctx['timeline'] = get_stages(event)
        return ctx
