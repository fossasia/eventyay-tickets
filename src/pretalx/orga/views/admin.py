import sys

from django.views.generic import TemplateView
from django_context_decorator import context

from pretalx.common.mixins.views import PermissionRequired


class AdminDashboard(PermissionRequired, TemplateView):
    template_name = 'orga/admin.html'
    permission_required = 'person.is_administrator'

    @context
    def executable(self):
        return sys.executable
