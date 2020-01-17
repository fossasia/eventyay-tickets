import sys

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView
from django_context_decorator import context

from pretalx.celery_app import app
from pretalx.common.mixins.views import PermissionRequired
from pretalx.common.models.settings import GlobalSettings
from pretalx.common.update_check import check_result_table, update_check
from pretalx.orga.forms.admin import UpdateSettingsForm


class AdminDashboard(PermissionRequired, TemplateView):
    template_name = "orga/admin.html"
    permission_required = "person.is_administrator"

    @context
    def queue_length(self):
        if not settings.HAS_CELERY:
            return None
        try:
            client = app.broker_connection().channel().client
            return client.llen("celery")
        except Exception as e:
            return str(e)

    @context
    def executable(self):
        return sys.executable


class UpdateCheckView(PermissionRequired, FormView):
    template_name = "orga/update.html"
    permission_required = "person.is_administrator"
    form_class = UpdateSettingsForm

    def post(self, request, *args, **kwargs):
        if "trigger" in request.POST:
            update_check.apply()
            return redirect(self.get_success_url())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _("Your changes have been saved."))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request, _("Your changes have not been saved, see below for errors.")
        )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        result = super().get_context_data()
        result["gs"] = GlobalSettings()
        result["gs"].settings.set("update_check_ack", True)
        return result

    @context
    def result_table(self):
        return check_result_table()

    def get_success_url(self):
        return reverse("orga:admin.update")
