import copy
import datetime
import json

import icalendar
import jwt
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import PermissionDenied
from eventyay.base.models.auth import User
from django.db import transaction
from django.db.models import Count, F, Max, OuterRef, Subquery
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
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

from eventyay.base.models import (
    BBBCall,
    BBBServer,
    SystemLog,
    JanusServer,
    JitsiServer,
    StreamingServer,
    TurnServer,
    Event,
)

from eventyay.base.models.event import EventPlannedUsage as PlannedUsage
from eventyay.base.services.bbb import get_url
from eventyay.control.forms.server_management import (
    BBBMoveRoomForm,
    BBBServerForm,
    JanusServerForm,
    JitsiServerForm,
    PlannedUsageFormSet,
    ProfileForm,
    SignupForm,
    StreamingServerForm,
    TurnServerForm,
    UserForm,
    EventForm,
)
from eventyay.base.models.log import LogEntry
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.control.tasks import clear_event_data
from eventyay.control.video.admin_dashboard import get_video_server_config


class SuperuserBase(AdministratorPermissionRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)


class UserList(SuperuserBase, ListView):
    template_name = "control/user_list.html"
    queryset = User.objects.all()
    context_object_name = "users"


class UserUpdate(SuperuserBase, UpdateView):
    template_name = "control/user_update.html"
    queryset = User.objects.all()
    context_object_name = "users"
    form_class = UserForm
    success_url = "/admin/video/users/"

    def form_valid(self, form):
        LogEntry.objects.create(
            content_object=self.object,
            user=self.request.user,
            action_type="user.changed",
            data={"changed_keys": form.changed_data},
        )
        return super().form_valid(form)


class SignupView(SuperuserBase, FormView):
    template_name = "registration/register.html"
    form_class = SignupForm

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            _("The user has been created successfully, they can now log in."),
        )
        return redirect("/admin/video/")


class ProfileView(AdministratorPermissionRequiredMixin, FormView):
    template_name = "control/profile.html"
    form_class = ProfileForm
    success_url = "/admin/video/auth/profile/"

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


class VideoSettings(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = "control/video_settings.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["bbb_servers"] = BBBServer.objects.select_related("event_exclusive").order_by("url")
        ctx["janus_servers"] = JanusServer.objects.select_related("event_exclusive").order_by("url")
        ctx["jitsi_servers"] = JitsiServer.objects.select_related("event_exclusive").order_by("url")
        ctx["turn_servers"] = TurnServer.objects.select_related("event_exclusive").order_by("hostname")
        ctx["streaming_servers"] = StreamingServer.objects.order_by("name")
        # Define the tabs logic, active tab can default to bbb
        ctx["active_tab"] = self.request.GET.get("tab", "bbb")
        return ctx


class VideoServerToggleActive(AdministratorPermissionRequiredMixin, View):
    def post(self, request, server_type, pk, *args, **kwargs):
        config = get_video_server_config(server_type)
        if not config:
            return JsonResponse(
                {"ok": False, "error": "Unknown video server type."},
                status=404,
            )

        try:
            payload = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            return JsonResponse(
                {"ok": False, "error": "Invalid JSON payload."},
                status=400,
            )

        active = payload.get("active")
        if not isinstance(active, bool):
            return JsonResponse(
                {"ok": False, "error": "The active value must be true or false."},
                status=400,
            )

        model = config.model
        try:
            server = model.objects.get(pk=pk)
        except model.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Video server not found."}, status=404)

        previous_active = bool(server.active)
        server.active = active
        server.save(update_fields=["active"])

        LogEntry.objects.create(
            content_object=server,
            user=request.user,
            action_type=f"{config.action_prefix}.active_changed",
            data=json.dumps(
                {
                    "active": active,
                    "previous_active": previous_active,
                }
            ),
        )

        return JsonResponse(
            {
                "ok": True,
                "active": active,
                "status": _("Active") if active else _("Inactive"),
            }
        )


class EventList(AdministratorPermissionRequiredMixin, ListView):
    template_name = "control/event_list.html"
    queryset = (
        Event.objects.annotate(
            user_count=Count("user"),
            last_usage=Subquery(
                PlannedUsage.objects.filter(event=OuterRef("pk"))
                .order_by()
                .values("event")
                .annotate(end=Max("end"))
                .values("end")
            ),
        )
        .prefetch_related("planned_usages")
        .order_by(
            F("last_usage").desc(nulls_last=True),
            F("domain").asc(nulls_last=True),
        )
    )
    context_object_name = "events"

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)

        for event in ctx["events"]:
            if event.config and event.config.get("JWT_secrets"):
                event.admin_token = True
        return ctx


class EventAdminToken(AdministratorPermissionRequiredMixin, DetailView):
    template_name = "control/event_clear.html"
    queryset = Event.objects.all()
    success_url = "/admin/video/events/"

    def get_object(self, queryset=None):
        """
        Override get_object to handle both slug and pk lookups
        """
        if queryset is None:
            queryset = self.get_queryset()

        pk = self.kwargs.get('pk')
        if pk is None:
            raise AttributeError("EventAdminToken view must be called with a pk argument.")

        # Try to get the object by pk first (if it's numeric)
        try:
            if pk.isdigit():
                return queryset.get(pk=pk)
        except Event.DoesNotExist:
            pass

        # If pk lookup fails or pk is not numeric, try slug lookup
        try:
            return queryset.get(slug=pk)
        except Event.DoesNotExist:
            from django.http import Http404
            raise Http404("Event not found")

    def get(self, request, *args, **kwargs):
        event = self.get_object()

        # Ensure JWT configuration exists
        if not event.config or not event.config.get("JWT_secrets"):
            from django.utils.crypto import get_random_string
            from django.conf import settings

            secret = get_random_string(length=64)
            event.config = {
                "JWT_secrets": [
                    {
                        "issuer": "any",
                        "audience": "eventyay",
                        "secret": secret,
                    }
                ]
            }
            event.save()

            # Also set up the video plugin settings for the video frontend
            try:
                event.settings.venueless_secret = secret
                event.settings.venueless_issuer = "any"
                event.settings.venueless_audience = "eventyay"
                # Point to SPA at /video/<event_slug>
                base_site = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
                event.settings.venueless_url = f"{base_site}/video/{event.slug}"
            except Exception:
                pass

        LogEntry.objects.create(
            content_object=event,
            user=self.request.user,
            action_type="event.adminaccess",
            data={},
        )

        return redirect(f"/video/event/{event.organizer.slug}/{event.slug}/")


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


class EventCreate(FormsetMixin, AdministratorPermissionRequiredMixin, CreateView):
    template_name = "control/event_create.html"
    form_class = EventForm
    success_url = "/admin/video/events/"

    @cached_property
    def copy_from(self):
        if self.request.GET.get("copy_from") and not getattr(self, "object", None):
            try:
                return Event.objects.get(pk=self.request.GET.get("copy_from"))
            except Event.DoesNotExist:
                pass

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.copy_from:
            inst = copy.copy(self.copy_from)
            inst.pk = None
            inst.domain = None
            # Generate a new unique slug to avoid IntegrityError
            base_slug = self.copy_from.slug
            counter = 1
            new_slug = f"{base_slug}-copy"
            while Event.objects.filter(organizer=self.copy_from.organizer, slug=new_slug).exists():
                new_slug = f"{base_slug}-copy-{counter}"
                counter += 1
            inst.slug = new_slug
            kwargs["instance"] = inst
        return kwargs

    @transaction.atomic()
    def form_valid(self, form):
        secret = get_random_string(length=64)
        form.instance.config = {
            "JWT_secrets": [
                {
                    "issuer": "any",
                    "audience": "eventyay",
                    "secret": secret,
                }
            ]
        }
        if self.copy_from:
            form.instance.clone_from(self.copy_from, new_secrets=True)
            form.instance.copy_data_from(self.copy_from)

        self.object = form.save()

        # Initialize Eventyay Video (ticket-video) defaults so the video frontend works immediately
        try:
            secret = form.instance.config["JWT_secrets"][0]["secret"]
            issuer = form.instance.config["JWT_secrets"][0]["issuer"]
            audience = form.instance.config["JWT_secrets"][0]["audience"]
            self.object.settings.venueless_secret = secret
            self.object.settings.venueless_issuer = issuer
            self.object.settings.venueless_audience = audience
            # Point to SPA at /video/<event_id>
            base_site = settings.SITE_URL.rstrip('/')
            self.object.settings.venueless_url = f"{base_site}/video/{self.object.pk}"
            if self.copy_from and self.copy_from.settings.get('event_type') == 'meetup':
                self.object.settings.set('meetup_video_active', True)
        except (KeyError, IndexError, TypeError, AttributeError):
            pass

        for f in self.formset.extra_forms:
            if not f.has_changed():
                continue
            if self.formset._should_delete_form(f):
                continue
            f.instance.event = self.object
            f.save()

        if self.copy_from:
            try:
                secret = form.instance.config["JWT_secrets"][0]["secret"]
                issuer = form.instance.config["JWT_secrets"][0]["issuer"]
                audience = form.instance.config["JWT_secrets"][0]["audience"]
                self.object.settings.venueless_secret = secret
                self.object.settings.venueless_issuer = issuer
                self.object.settings.venueless_audience = audience
                base_site = settings.SITE_URL.rstrip('/')
                self.object.settings.venueless_url = f"{base_site}/video/{self.object.pk}"
            except (KeyError, IndexError, TypeError, AttributeError):
                pass

        LogEntry.objects.create(
            content_object=form.instance,
            user=self.request.user,
            action_type="event.created",
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


class EventUpdate(FormsetMixin, AdministratorPermissionRequiredMixin, UpdateView):
    template_name = "control/event_update.html"
    form_class = EventForm
    queryset = Event.objects.all()
    success_url = "/admin/video/events/"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        config = self.object.config or {}
        ctx["jwtconf"] = json.dumps(config.get("JWT_secrets", []), indent=4)
        return ctx

    def form_valid(self, form):
        self.formset.save()
        LogEntry.objects.create(
            content_object=self.get_object(),
            user=self.request.user,
            action_type="event.updated",
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


class EventClear(AdministratorPermissionRequiredMixin, DetailView):
    template_name = "control/event_clear.html"
    queryset = Event.objects.all()
    success_url = "/admin/video/events/"

    def post(self, request, *args, **kwargs):
        LogEntry.objects.create(
            content_object=self.get_object(),
            user=self.request.user,
            action_type="event.cleared",
            data={},
        )
        clear_event_data.apply_async(kwargs={"event": self.get_object().pk})
        messages.success(request, _("The data will soon be deleted."))
        return redirect(self.success_url)





class BBBServerCreate(AdministratorPermissionRequiredMixin, CreateView):
    template_name = "control/bbb_form.html"
    form_class = BBBServerForm
    success_url = "/admin/video/bbbs/"

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


class BBBServerUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    template_name = "control/bbb_form.html"
    form_class = BBBServerForm
    queryset = BBBServer.objects.all()
    success_url = "/admin/video/bbbs/"

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


class BBBServerDelete(AdministratorPermissionRequiredMixin, DeleteView):
    template_name = "control/bbb_delete.html"
    queryset = BBBServer.objects.all()
    success_url = "/admin/video/bbbs/"
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





class JanusServerCreate(AdministratorPermissionRequiredMixin, CreateView):
    template_name = "control/janus_form.html"
    form_class = JanusServerForm
    success_url = "/admin/video/janus/"

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


class JanusServerUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    template_name = "control/janus_form.html"
    form_class = JanusServerForm
    queryset = JanusServer.objects.all()
    success_url = "/admin/video/janus/"

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


class JanusServerDelete(AdministratorPermissionRequiredMixin, DeleteView):
    template_name = "control/janus_delete.html"
    queryset = JanusServer.objects.all()
    success_url = "/admin/video/janus/"
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





class JitsiServerCreate(AdministratorPermissionRequiredMixin, CreateView):
    template_name = "control/jitsi_form.html"
    form_class = JitsiServerForm
    success_url = "/admin/video/jitsi/"

    @transaction.atomic()
    def form_valid(self, form):
        self.object = form.save()

        LogEntry.objects.create(
            content_object=form.instance,
            user=self.request.user,
            action_type="jitsiserver.created",
            data=_redact_jitsi_server_log_data(form.cleaned_data),
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class JitsiServerUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    template_name = "control/jitsi_form.html"
    form_class = JitsiServerForm
    queryset = JitsiServer.objects.all()
    success_url = "/admin/video/jitsi/"

    def form_valid(self, form):
        self.object = form.save()

        LogEntry.objects.create(
            content_object=form.instance,
            user=self.request.user,
            action_type="jitsiserver.updated",
            data=_redact_jitsi_server_log_data(form.cleaned_data),
        )
        messages.success(self.request, _("Ok!"))
        return super().form_valid(form)


class JitsiServerDelete(AdministratorPermissionRequiredMixin, DeleteView):
    template_name = "control/jitsi_delete.html"
    queryset = JitsiServer.objects.all()
    success_url = "/admin/video/jitsi/"
    context_object_name = "server"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        LogEntry.objects.create(
            content_object=self.object,
            user=self.request.user,
            action_type="jitsiserver.deleted",
            data={},
        )
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(self.request, _("Ok!"))
        return HttpResponseRedirect(success_url)


def _redact_jitsi_server_log_data(data):
    return {
        key: "*****" if key == "app_secret" and value else str(value)
        for key, value in data.items()
    }





class TurnServerCreate(AdministratorPermissionRequiredMixin, CreateView):
    template_name = "control/turn_form.html"
    form_class = TurnServerForm
    success_url = "/admin/video/turns/"

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


class TurnServerUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    template_name = "control/turn_form.html"
    form_class = TurnServerForm
    queryset = TurnServer.objects.all()
    success_url = "/admin/video/turns/"

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


class TurnServerDelete(AdministratorPermissionRequiredMixin, DeleteView):
    template_name = "control/turn_delete.html"
    queryset = TurnServer.objects.all()
    success_url = "/admin/video/turns/"
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


class SystemLogList(AdministratorPermissionRequiredMixin, ListView):
    template_name = "control/systemlog_list.html"
    queryset = SystemLog.objects.order_by("-timestamp")
    context_object_name = "systemlogs"
    paginate_by = 25


class SystemLogDetail(AdministratorPermissionRequiredMixin, DetailView):
    template_name = "control/systemlog_detail.html"
    queryset = SystemLog.objects.all()
    context_object_name = "systemlog"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["trace"] = json.loads(self.object.trace)
        return ctx


class EventCalendar(AdministratorPermissionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        queryset = PlannedUsage.objects.all().select_related("event")
        calendar = icalendar.Calendar()
        for planned_usage in queryset:
            calendar.add_component(planned_usage.as_ical())

        return HttpResponse(
            calendar.to_ical(),
            content_type="text/calendar",
            headers={"Content-Disposition": 'attachment; filename="eventyay.ics"'},
        )





class StreamingServerCreate(AdministratorPermissionRequiredMixin, CreateView):
    template_name = "control/streaming_form.html"
    form_class = StreamingServerForm
    success_url = "/admin/video/streamingservers/"

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


class StreamingServerUpdate(AdministratorPermissionRequiredMixin, UpdateView):
    template_name = "control/streaming_form.html"
    form_class = StreamingServerForm
    queryset = StreamingServer.objects.all()
    success_url = "/admin/video/streamingservers/"

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


class StreamingServerDelete(AdministratorPermissionRequiredMixin, DeleteView):
    template_name = "control/streaming_delete.html"
    queryset = StreamingServer.objects.all()
    success_url = "/admin/video/streamingservers/"
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




class BBBMoveRoom(AdministratorPermissionRequiredMixin, FormView):
    template_name = "control/bbb_moveroom.html"
    form_class = BBBMoveRoomForm

    def form_valid(self, form):
        server = form.cleaned_data["server"]
        room = form.cleaned_data["room"]

        try:
            c = BBBCall.objects.get(room=room)
        except BBBCall.DoesNotExist:
            messages.error(self.request, _("No BBB session found for this room."))
            return HttpResponseRedirect(self.request.path)
        source_server = c.server
        try:
            u = get_url(
                "end",
                {"meetingID": c.meeting_id, "password": c.moderator_pw},
                source_server.url,
                source_server.secret,
            )
            r = requests.get(u, timeout=15)
            r.raise_for_status()
        except Exception:
            messages.warning(self.request, _("Kicking all attendees did not work."))

        c.server = server
        c.save()
        messages.success(self.request, _("Moved."))
        return HttpResponseRedirect(self.request.path)
