from django.shortcuts import redirect
from django.views.generic import TemplateView

from pretalx.orga.authorization import OrgaPermissionRequired


class DashboardView(TemplateView):
    template_name = 'orga/dashboard.html'

    def dispatch(self, request):
        if request.user.is_anonymous:
            return redirect('orga:login')

        return super().dispatch(request)


class EventDashboardView(OrgaPermissionRequired, TemplateView):
    template_name = 'orga/event/dashboard.html'
