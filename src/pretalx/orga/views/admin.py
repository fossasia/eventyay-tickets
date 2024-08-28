import sys

from csp.decorators import csp_update
from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, FormView, ListView, TemplateView
from django_context_decorator import context
from django_scopes import scopes_disabled

from pretalx.celery_app import app
from pretalx.common.mixins.views import ActionConfirmMixin, PermissionRequired
from pretalx.common.models.settings import GlobalSettings
from pretalx.common.text.phrases import phrases
from pretalx.common.update_check import check_result_table, update_check
from pretalx.orga.forms.admin import UpdateSettingsForm
from pretalx.person.models import User


class AdminDashboard(PermissionRequired, TemplateView):
    template_name = "orga/admin.html"
    permission_required = "person.is_administrator"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site_name = dict(settings.CONFIG.items("site")).get("name")
        context["site_name"] = site_name
        return context

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

    @context
    def pretalx_version(self):
        return settings.PRETALX_VERSION


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
        result = super().get_context_data(**kwargs)
        result["gs"] = GlobalSettings()
        result["gs"].settings.set("update_check_ack", True)
        return result

    @context
    def result_table(self):
        return check_result_table()

    def get_success_url(self):
        return reverse("orga:admin.update")


class AdminUserList(PermissionRequired, ListView):
    template_name = "orga/admin/user_list.html"
    permission_required = "person.is_administrator"
    model = User
    context_object_name = "users"
    paginate_by = "250"

    def dispatch(self, *args, **kwargs):
        with scopes_disabled():
            return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        search = self.request.GET.get("q", "").strip()
        if not search or len(search) < 3:
            return User.objects.none()
        return (
            User.objects.filter(Q(name__icontains=search) | Q(email__icontains=search))
            .prefetch_related(
                "teams",
                "teams__organiser",
                "teams__organiser__events",
                "teams__limit_events",
            )
            .annotate(
                submission_count=Count("submissions", distinct=True),
            )
        )

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action") or "-"
        action, user_id = action.split("-")
        user = User.objects.get(pk=user_id)
        if action == "reset":
            user.reset_password(event=None)
            messages.success(request, phrases.base.password_reset_success)
        elif action == "delete":
            return redirect(
                reverse("orga:admin.user.delete", kwargs={"code": user.code})
            )
        return super().get(request, *args, **kwargs)


class AdminUserDetail(PermissionRequired, DetailView):
    template_name = "orga/admin/user_detail.html"
    permission_required = "person.is_administrator"
    model = User
    context_object_name = "user"
    slug_url_kwarg = "code"
    slug_field = "code"

    @csp_update(IMG_SRC="https://www.gravatar.com")
    def dispatch(self, *args, **kwargs):
        with scopes_disabled():
            return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action") or "-"
        if action == "pw-reset":
            self.get_object().reset_password(event=None)
            messages.success(request, phrases.base.password_reset_success)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("orga:admin.user.list")

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result["teams"] = self.object.teams.all().prefetch_related(
            "organiser", "limit_events", "organiser__events"
        )
        result["submissions"] = self.object.submissions.all()
        return result


class AdminUserDelete(ActionConfirmMixin, AdminUserDetail):

    @property
    def action_object_name(self):
        return _("User") + f": {self.get_object().name}"

    @property
    def action_next_url(self):
        return self.get_success_url()

    @property
    def action_back_url(self):
        return f"/orga/admin/users/{self.get_object().code}/"

    def dispatch(self, *args, **kwargs):
        with scopes_disabled():
            return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.get_object().shred()
        messages.success(request, _("The user has been deleted."))
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("orga:admin.user.list")
