import sys

from django.conf import settings
from django.views.generic import TemplateView
from django_context_decorator import context

from pretalx.celery_app import app
from pretalx.common.mixins.views import PermissionRequired


class AdminDashboard(PermissionRequired, TemplateView):
    template_name = 'orga/admin.html'
    permission_required = 'person.is_administrator'

    @context
    def queue_length(self):
        if settings.HAS_CELERY:
            try:
                client = app.broker_connection().channel().client
                return client.llen('celery')
            except Exception as e:
                return str(e)

    @context
    def executable(self):
        return sys.executable
