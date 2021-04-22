import copy
import datetime
import json

import jwt
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, F, OuterRef, Subquery
from django.shortcuts import redirect
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from venueless.core.models import RoomView, World

from .forms import ProfileForm, SignupForm, UserForm, WorldForm
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
    queryset = World.objects.annotate(
        user_count=Count("user"),
        current_view_count=Subquery(
            RoomView.objects.filter(room__world=OuterRef("pk"), end__isnull=True)
            .order_by()
            .values("room__world")
            .annotate(c=Count("*"))
            .values("c")
        ),
    ).order_by(F("current_view_count").desc(nulls_last=True))
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


class WorldCreate(AdminBase, CreateView):
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

        form.save()
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


class WorldUpdate(AdminBase, UpdateView):
    template_name = "control/world_update.html"
    form_class = WorldForm
    queryset = World.objects.all()
    success_url = "/control/worlds/"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["jwtconf"] = json.dumps(self.object.config.get("JWT_secrets", []), indent=4)
        return ctx

    def form_valid(self, form):
        LogEntry.objects.create(
            content_object=self.get_object(),
            user=self.request.user,
            action_type="world.updated",
            data=form.cleaned_data,
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


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
