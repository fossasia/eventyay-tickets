from django.views.generic import TemplateView

from pretalx.common.mixins.views import PermissionRequired
from pretalx.event.stages import get_stages


class DashboardView(TemplateView):
    template_name = 'orga/dashboard.html'


class EventDashboardView(PermissionRequired, TemplateView):
    template_name = 'orga/event/dashboard.html'
    permission_required = 'orga.view_orga_area'

    def get_object(self):
        return self.request.event

    def get_context_data(self, event):
        ctx = super().get_context_data()
        ctx['timeline'] = get_stages(self.request.event)
        return ctx
