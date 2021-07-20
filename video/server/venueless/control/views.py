import copy
import datetime
import json

import icalendar
import jwt
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, F, Max, OuterRef, Subquery
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from venueless.core.models import (
    BBBServer,
    Feedback,
    JanusServer,
    RoomView,
    StreamingServer,
    TurnServer,
    World,
)

from ..core.models.world import PlannedUsage
from .forms import (
    BBBServerForm,
    JanusServerForm,
    PlannedUsageFormSet,
    ProfileForm,
    SignupForm,
    StreamingServerForm,
    StreamKeyGeneratorForm,
    TurnServerForm,
    UserForm,
    WorldForm,
)
from .models import LogEntry
from .tasks import clear_world_data


class SuperuserBase(UserPassesTestMixin):
    login_url = "/control/auth/login/"

    def test_func(self):
        return self.request.user.is_superuser


class UserList(SuperuserBase, ListView):
    template_name = "control/user_list.html"
    queryset = User.objects.all()
    context_object_name = "users"


class UserUpdate(SuperuserBase, UpdateView):
    template_name = "control/user_update.html"
    queryset = User.objects.all()
    context_object_name = "users"
    form_class = UserForm
    success_url = "/control/users/"

    def form_valid(self, form):
        LogEntry.objects.create(
            content_object=self.object,
            user=self.request.user,
            action_type="user.changed",
            data={"changed_keys": form.changed_data},
        )
        return super().form_valid(form)


class AdminBase(UserPassesTestMixin):
    """Simple View mixin for now, but will make it easier to
    improve permissions in the future."""

    login_url = "/control/auth/login/"

    def test_func(self):
        secret_key = self.request.GET.get("control_token")
        if secret_key and secret_key == settings.CONTROL_SECRET:
            return True
        return self.request.user.is_staff


class SignupView(AdminBase, FormView):
    template_name = "registration/register.html"
    form_class = SignupForm

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            _("The user has been created successfully, they can now log in."),
        )
        return redirect("/control/")


class ProfileView(AdminBase, FormView):
    template_name = "control/profile.html"
    form_class = ProfileForm
    success_url = "/control/auth/profile/"

    def form_valid(self, form):
        LogEntry.objects.create(
            content_object=self.request.user,
            user=self.request.user,
            action_type="profile.changed",
            data={"changed_keys": form.changed_data},
        )
        form.save()
        update_session_auth_hash(self.request, self.request.user)
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["instance"] = self.request.user
        return result


class IndexView(AdminBase, TemplateView):
    template_name = "control/index.html"


class WorldList(AdminBase, ListView):
    template_name = "control/world_list.html"
    queryset = (
        World.objects.annotate(
            user_count=Count("user"),
            current_view_count=Subquery(
                RoomView.objects.filter(
                    room__world=OuterRef("pk"),
                    start__gt=now() - datetime.timedelta(hours=24),
                    end__isnull=True,
                )
                .order_by()
                .values("room__world")
                .annotate(c=Count("*"))
                .values("c")
            ),
            last_usage=Subquery(
                PlannedUsage.objects.filter(world=OuterRef("pk"))
                .order_by()
                .values("world")
                .annotate(end=Max("end"))
                .values("end")
            ),
        )
        .prefetch_related("planned_usages")
        .order_by(
            F("current_view_count").desc(nulls_last=True),
            F("last_usage").desc(nulls_last=True),
        )
    )
    context_object_name = "worlds"

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)

        for world in ctx["worlds"]:
            if world.config and world.config.get("JWT_secrets"):
                world.admin_token = True
        return ctx


class WorldAdminToken(AdminBase, DetailView):
    template_name = "control/world_clear.html"
    queryset = World.objects.all()
    success_url = "/control/worlds/"

    def get(self, request, *args, **kwargs):
        world = self.get_object()
        jwt_config = world.config["JWT_secrets"][0]
        secret = jwt_config["secret"]
        audience = jwt_config["audience"]
        issuer = jwt_config["issuer"]
        iat = datetime.datetime.utcnow()
        exp = iat + datetime.timedelta(days=7)
        payload = {
            "iss": issuer,
            "aud": audience,
            "exp": exp,
            "iat": iat,
            "uid": "__admin__",
            "traits": ["admin"],
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        LogEntry.objects.create(
            content_object=world,
            user=self.request.user,
            action_type="world.adminaccess",
            data={},
        )
        return redirect(f"https://{world.domain}/#token={token}")


class FormsetMixin:
    @cached_property
    def formset(self):
        return PlannedUsageFormSet(
            data=self.request.POST if self.request.method == "POST" else None,
            instance=self.object,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["formset"] = self.formset
        return ctx


class WorldCreate(FormsetMixin, AdminBase, CreateView):
    template_name = "control/world_create.html"
    form_class = WorldForm
    success_url = "/control/worlds/"

    @cached_property
    def copy_from(self):
        if self.request.GET.get("copy_from") and not getattr(self, "object", None):
            try:
                return World.objects.get(pk=self.request.GET.get("copy_from"))
            except World.DoesNotExist:
                pass

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.copy_from:
            inst = copy.copy(self.copy_from)
            inst.pk = None
            inst.domain = None
            kwargs["instance"] = inst
        return kwargs

    @transaction.atomic()
    def form_valid(self, form):
        secret = get_random_string(length=64)
        form.instance.config = {
            "JWT_secrets": [
                {
                    "issuer": "any",
                    "audience": "venueless",
                    "secret": secret,
                }
            ]
        }
        if self.copy_from:
            form.instance.clone_from(self.copy_from, new_secrets=True)

        self.object = form.save()

        for f in self.formset.extra_forms:
            if not f.has_changed():
                continue
            if self.formset._should_delete_form(f):
                continue
            f.instance.world = self.object
            f.save()

        LogEntry.objects.create(
            content_object=form.instance,
            user=self.request.user,
            action_type="world.created",
            data={
                "copy_from": self.copy_from.pk if self.copy_from else None,
                **form.cleaned_data,
            },
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["copy_from"] = self.copy_from
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        if form.is_valid() and self.formset.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


class WorldUpdate(FormsetMixin, AdminBase, UpdateView):
    template_name = "control/world_update.html"
    form_class = WorldForm
    queryset = World.objects.all()
    success_url = "/control/worlds/"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["jwtconf"] = json.dumps(self.object.config.get("JWT_secrets", []), indent=4)
        return ctx

    def form_valid(self, form):
        self.formset.save()
        LogEntry.objects.create(
            content_object=self.get_object(),
            user=self.request.user,
            action_type="world.updated",
            data=form.cleaned_data,
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid() and self.formset.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


class WorldClear(AdminBase, DetailView):
    template_name = "control/world_clear.html"
    queryset = World.objects.all()
    success_url = "/control/worlds/"

    def post(self, request, *args, **kwargs):
        LogEntry.objects.create(
            content_object=self.get_object(),
            user=self.request.user,
            action_type="world.cleared",
            data={},
        )
        clear_world_data.apply_async(kwargs={"world": self.get_object().pk})
        messages.success(request, _("The data will soon be deleted."))
        return redirect(self.success_url)


class BBBServerList(AdminBase, ListView):
    template_name = "control/bbb_list.html"
    queryset = BBBServer.objects.select_related("world_exclusive").order_by("url")
    context_object_name = "servers"


class BBBServerCreate(AdminBase, CreateView):
    template_name = "control/bbb_form.html"
    form_class = BBBServerForm
    success_url = "/control/bbbs/"

    @transaction.atomic()
    def form_valid(self, form):
        self.object = form.save()

        LogEntry.objects.create(
            content_object=form.instance,
            user=self.request.user,
            action_type="bbbserver.created",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class BBBServerUpdate(AdminBase, UpdateView):
    template_name = "control/bbb_form.html"
    form_class = BBBServerForm
    queryset = BBBServer.objects.all()
    success_url = "/control/bbbs/"

    def form_valid(self, form):
        self.object = form.save()

        LogEntry.objects.create(
            content_object=form.instance,
            user=self.request.user,
            action_type="bbbserver.updated",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class BBBServerDelete(AdminBase, DeleteView):
    template_name = "control/bbb_delete.html"
    queryset = BBBServer.objects.all()
    success_url = "/control/bbbs/"
    context_object_name = "server"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        LogEntry.objects.create(
            content_object=self.object,
            user=self.request.user,
            action_type="bbbserver.deleted",
            data={},
        )
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(self.request, _("Ok!"))
        return HttpResponseRedirect(success_url)


class JanusServerList(AdminBase, ListView):
    template_name = "control/janus_list.html"
    queryset = JanusServer.objects.select_related("world_exclusive").order_by("url")
    context_object_name = "servers"


class JanusServerCreate(AdminBase, CreateView):
    template_name = "control/janus_form.html"
    form_class = JanusServerForm
    success_url = "/control/janus/"

    @transaction.atomic()
    def form_valid(self, form):
        self.object = form.save()

        LogEntry.objects.create(
            content_object=form.instance,
            user=self.request.user,
            action_type="janusserver.created",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class JanusServerUpdate(AdminBase, UpdateView):
    template_name = "control/janus_form.html"
    form_class = JanusServerForm
    queryset = JanusServer.objects.all()
    success_url = "/control/janus/"

    def form_valid(self, form):
        self.object = form.save()

        LogEntry.objects.create(
            content_object=form.instance,
            user=self.request.user,
            action_type="janusserver.updated",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class JanusServerDelete(AdminBase, DeleteView):
    template_name = "control/janus_delete.html"
    queryset = JanusServer.objects.all()
    success_url = "/control/janus/"
    context_object_name = "server"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        LogEntry.objects.create(
            content_object=self.object,
            user=self.request.user,
            action_type="janusserver.deleted",
            data={},
        )
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(self.request, _("Ok!"))
        return HttpResponseRedirect(success_url)


class TurnServerList(AdminBase, ListView):
    template_name = "control/turn_list.html"
    queryset = TurnServer.objects.select_related("world_exclusive").order_by("hostname")
    context_object_name = "servers"


class TurnServerCreate(AdminBase, CreateView):
    template_name = "control/turn_form.html"
    form_class = TurnServerForm
    success_url = "/control/turns/"

    @transaction.atomic()
    def form_valid(self, form):
        self.object = form.save()

        LogEntry.objects.create(
            content_object=form.instance,
            user=self.request.user,
            action_type="turnserver.created",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class TurnServerUpdate(AdminBase, UpdateView):
    template_name = "control/turn_form.html"
    form_class = TurnServerForm
    queryset = TurnServer.objects.all()
    success_url = "/control/turns/"

    def form_valid(self, form):
        self.object = form.save()

        LogEntry.objects.create(
            content_object=form.instance,
            user=self.request.user,
            action_type="turnserver.updated",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class TurnServerDelete(AdminBase, DeleteView):
    template_name = "control/turn_delete.html"
    queryset = TurnServer.objects.all()
    success_url = "/control/turns/"
    context_object_name = "server"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        LogEntry.objects.create(
            content_object=self.object,
            user=self.request.user,
            action_type="turnserver.deleted",
            data={},
        )
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(self.request, _("Ok!"))
        return HttpResponseRedirect(success_url)


class FeedbackList(AdminBase, ListView):
    template_name = "control/feedback_list.html"
    queryset = Feedback.objects.order_by("-timestamp")
    context_object_name = "feedbacks"
    paginate_by = 25


class FeedbackDetail(AdminBase, DetailView):
    template_name = "control/feedback_detail.html"
    queryset = Feedback.objects.all()
    context_object_name = "feedback"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["trace"] = json.loads(self.object.trace)
        return ctx


class WorldCalendar(AdminBase, View):
    def get(self, request, *args, **kwargs):
        queryset = PlannedUsage.objects.all().select_related("world")
        calendar = icalendar.Calendar()
        for planned_usage in queryset:
            calendar.add_component(planned_usage.as_ical())

        return HttpResponse(
            calendar.to_ical(),
            content_type="text/calendar",
            headers={"Content-Disposition": 'attachment; filename="venueless.ics"'},
        )


class StreamingServerList(AdminBase, ListView):
    template_name = "control/streaming_list.html"
    queryset = StreamingServer.objects.order_by("name")
    context_object_name = "streamings"


class StreamingServerCreate(AdminBase, CreateView):
    template_name = "control/streaming_form.html"
    form_class = StreamingServerForm
    success_url = "/control/streamingservers/"

    @transaction.atomic()
    def form_valid(self, form):
        self.object = form.save()

        LogEntry.objects.create(
            content_object=form.instance,
            user=self.request.user,
            action_type="streamingserver.created",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class StreamingServerUpdate(AdminBase, UpdateView):
    template_name = "control/streaming_form.html"
    form_class = StreamingServerForm
    queryset = StreamingServer.objects.all()
    success_url = "/control/streamingservers/"

    def form_valid(self, form):
        self.object = form.save()

        LogEntry.objects.create(
            content_object=form.instance,
            user=self.request.user,
            action_type="streamingserver.updated",
            data={k: str(v) for k, v in form.cleaned_data.items()},
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class StreamingServerDelete(AdminBase, DeleteView):
    template_name = "control/streaming_delete.html"
    queryset = StreamingServer.objects.all()
    success_url = "/control/streamingservers/"
    context_object_name = "server"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        LogEntry.objects.create(
            content_object=self.object,
            user=self.request.user,
            action_type="streamingserver.deleted",
            data={},
        )
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(self.request, _("Ok!"))
        return HttpResponseRedirect(success_url)


class StreamkeyGenerator(AdminBase, FormView):
    template_name = "control/streamkey.html"
    form_class = StreamKeyGeneratorForm

    def form_valid(self, form):
        return self.get(self.request, *self.args, **self.kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx["form"]
        if self.request.method == "POST" and form.is_valid():
            ctx["result"] = form.cleaned_data["server"].generate_streamkey(
                form.cleaned_data["name"],
                form.cleaned_data["days"],
            )
        return ctx
