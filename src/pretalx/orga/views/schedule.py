import collections
import datetime as dt
import json
from contextlib import suppress

import dateutil.parser
from csp.decorators import csp_update
from django.conf import settings
from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, TemplateView, UpdateView, View
from django_context_decorator import context
from i18nfield.strings import LazyI18nString
from i18nfield.utils import I18nJSONEncoder

from pretalx.agenda.management.commands.export_schedule_html import get_export_zip_path
from pretalx.agenda.tasks import export_schedule_html
from pretalx.common.language import get_current_language_information
from pretalx.common.mixins.views import (
    ActionFromUrl,
    EventPermissionRequired,
    PermissionRequired,
)
from pretalx.common.signals import register_data_exporters
from pretalx.common.utils import safe_filename
from pretalx.common.views import CreateOrUpdateView, OrderModelView
from pretalx.orga.forms.schedule import (
    ScheduleExportForm,
    ScheduleReleaseForm,
    ScheduleRoomForm,
    ScheduleVersionForm,
)
from pretalx.schedule.forms import QuickScheduleForm, RoomForm
from pretalx.schedule.models import Availability, Room, TalkSlot
from pretalx.schedule.utils import guess_schedule_version

SCRIPT_SRC = "'self' 'unsafe-eval'"
DEFAULT_SRC = "'self'"


if settings.VITE_DEV_MODE:
    SCRIPT_SRC = (f"{SCRIPT_SRC} {settings.VITE_DEV_SERVER}",)
    DEFAULT_SRC = (
        f"{DEFAULT_SRC} {settings.VITE_DEV_SERVER} {settings.VITE_DEV_SERVER.replace('http', 'ws')}",
    )


@method_decorator(
    csp_update(SCRIPT_SRC=SCRIPT_SRC, DEFAULT_SRC=DEFAULT_SRC), name="dispatch"
)
class ScheduleView(EventPermissionRequired, TemplateView):
    template_name = "orga/schedule/index.html"
    permission_required = "orga.view_schedule"

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        version = self.request.GET.get("version")

        # get current translations language from django
        language_information = get_current_language_information()
        path = language_information.get("path", language_information.get("code"))
        result["gettext_language"] = path.replace("-", "_")

        result["schedule_version"] = version
        result["schedule_version_form"] = ScheduleVersionForm(
            {"version": version} if version else None,
            event=self.request.event,
        )
        result["schedule_room_form"] = ScheduleRoomForm(
            (
                {"room": self.request.GET.getlist("room")}
                if "room" in self.request.GET
                else None
            ),
            event=self.request.event,
        )
        result["active_schedule"] = (
            self.request.event.schedules.filter(version=version).first()
            if version
            else self.request.event.wip_schedule
        )
        return result


class ScheduleExportView(EventPermissionRequired, FormView):
    template_name = "orga/schedule/export.html"
    permission_required = "orga.view_schedule"
    form_class = ScheduleExportForm

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["event"] = self.request.event
        return result

    @context
    def exporters(self):
        return list(
            exporter(self.request.event)
            for _, exporter in register_data_exporters.send(self.request.event)
            if exporter.group != "speaker"
        )

    def form_valid(self, form):
        result = form.export_data()
        if not result:
            messages.success(self.request, _("No data to be exported"))
            return redirect(self.request.path)
        return result


class ScheduleExportTriggerView(EventPermissionRequired, View):
    permission_required = "orga.view_schedule"

    def post(self, request, event):
        if settings.HAS_CELERY:
            export_schedule_html.apply_async(kwargs={"event_id": self.request.event.id})
            messages.success(
                self.request,
                _("A new export is being generated and will be available soon."),
            )
        else:
            self.request.event.cache.set("rebuild_schedule_export", True, None)
            messages.success(
                self.request,
                _(
                    "A new export will be generated on the next scheduled opportunity – please contact your administrator for details."
                ),
            )

        return redirect(self.request.event.orga_urls.schedule_export)


class ScheduleExportDownloadView(EventPermissionRequired, View):
    permission_required = "orga.view_schedule"

    def get(self, request, event):
        try:
            zip_path = get_export_zip_path(self.request.event)
            response = FileResponse(open(zip_path, "rb"), as_attachment=True)
        except Exception as e:
            messages.error(
                request,
                _(
                    "Could not find the current export, please try to regenerate it. ({error})"
                ).format(error=str(e)),
            )
            return redirect(self.request.event.orga_urls.schedule_export)
        response["Content-Disposition"] = "attachment; filename=" + safe_filename(
            zip_path.name
        )
        return response


class ScheduleReleaseView(EventPermissionRequired, FormView):
    form_class = ScheduleReleaseForm
    permission_required = "orga.release_schedule"
    template_name = "orga/schedule/release.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        kwargs["locales"] = self.request.event.locales
        return kwargs

    @context
    def warnings(self):
        return self.request.event.wip_schedule.warnings

    @context
    def changes(self):
        return self.request.event.wip_schedule.changes

    @context
    def notifications(self):
        return len(self.request.event.wip_schedule.generate_notifications(save=False))

    @context
    def suggested_version(self):
        return guess_schedule_version(self.request.event)

    def form_invalid(self, form):
        messages.error(
            self.request, _("You have to provide a new, unique schedule version!")
        )
        return redirect(self.request.event.orga_urls.release_schedule)

    def form_valid(self, form):
        self.request.event.release_schedule(
            form.cleaned_data["version"],
            user=self.request.user,
            notify_speakers=form.cleaned_data["notify_speakers"],
            comment=form.cleaned_data["comment"],
        )
        messages.success(self.request, _("Nice, your schedule has been released!"))
        return redirect(self.request.event.orga_urls.schedule)


class ScheduleResetView(EventPermissionRequired, View):
    permission_required = "orga.edit_schedule"

    def dispatch(self, request, event):
        super().dispatch(request, event)
        schedule_version = self.request.GET.get("version")
        schedule = self.request.event.schedules.filter(version=schedule_version).first()
        if schedule:
            schedule.unfreeze(user=request.user)
            messages.success(
                self.request,
                _(
                    "Reset successful – start editing the schedule from your selected version!"
                ),
            )
        else:
            messages.error(
                self.request, _("Error retrieving the schedule version to reset to.")
            )
        return redirect(self.request.event.orga_urls.schedule)


class ScheduleToggleView(EventPermissionRequired, View):
    permission_required = "orga.edit_schedule"

    def dispatch(self, request, event):
        super().dispatch(request, event)
        self.request.event.feature_flags["show_schedule"] = (
            not self.request.event.feature_flags["show_schedule"]
        )
        self.request.event.save()
        return redirect(self.request.event.orga_urls.schedule)


class ScheduleResendMailsView(EventPermissionRequired, View):
    permission_required = "orga.edit_schedule"

    def dispatch(self, request, event):
        super().dispatch(request, event)
        if self.request.event.current_schedule:
            mails = self.request.event.current_schedule.generate_notifications(
                save=True
            )
            messages.success(
                self.request,
                _(
                    "{count} emails have been saved to the outbox – you can make individual changes there or just send them all."
                ).format(count=len(mails)),
            )
        else:
            messages.warning(
                self.request,
                _(
                    "You can only regenerate mails after the first schedule was released."
                ),
            )
        return redirect(self.request.event.orga_urls.schedule)


def serialize_break(slot):
    return {
        "id": slot.pk,
        "title": slot.description.data if slot.description else "",
        "description": "",
        "room": slot.room.pk if slot.room else None,
        "start": slot.start.isoformat() if slot.start else None,
        "end": slot.end.isoformat() if slot.end else None,
        "duration": slot.duration,
        "updated": slot.updated.isoformat(),
    }


def serialize_slot(slot, warnings=None):
    base_data = serialize_break(slot)
    if slot.submission:
        submission_data = {
            "id": slot.pk,
            "title": str(slot.submission.title),
            "speakers": [
                {"name": speaker.name} for speaker in slot.submission.speakers.all()
            ],
            "submission_type": str(slot.submission.submission_type.name),
            "track": (
                {
                    "name": str(slot.submission.track.name),
                    "color": slot.submission.track.color,
                }
                if slot.submission.track
                else None
            ),
            "state": slot.submission.state,
            "description": str(slot.submission.description),
            "abstract": str(slot.submission.abstract),
            "notes": slot.submission.notes,
            "duration": slot.submission.duration
            or slot.submission.submission_type.default_duration,
            "content_locale": slot.submission.content_locale,
            "do_not_record": slot.submission.do_not_record,
            "room": slot.room.pk if slot.room else None,
            "start": slot.local_start.isoformat() if slot.start else None,
            "end": slot.local_end.isoformat() if slot.end else None,
            "url": slot.submission.orga_urls.base,
            "warnings": warnings or [],
        }
        return {**base_data, **submission_data}
    return base_data


class TalkList(EventPermissionRequired, View):
    permission_required = "orga.edit_schedule"

    def get(self, request, event):
        version = self.request.GET.get("version")
        schedule = None
        if version:
            schedule = request.event.schedules.filter(version=version).first()
        if not schedule:
            schedule = request.event.wip_schedule

        filter_updated = request.GET.get("since")
        result = schedule.build_data(
            all_talks=True,
            all_rooms=not bool(filter_updated),
            filter_updated=filter_updated,
        )

        if request.GET.get("warnings"):
            result["warnings"] = {
                talk.submission.code: warnings
                for talk, warnings in schedule.get_all_talk_warnings(
                    filter_updated=filter_updated
                ).items()
            }
        result["now"] = now().strftime("%Y-%m-%d %H:%M:%S%z")
        result["locales"] = request.event.locales
        return JsonResponse(result, encoder=I18nJSONEncoder)

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, event):
        data = json.loads(request.body.decode())
        start = (
            dateutil.parser.parse(data.get("start"))
            if data.get("start")
            else request.event.datetime_from
        )
        end = (
            dateutil.parser.parse(data.get("end"))
            if data.get("end")
            else start + dt.timedelta(minutes=int(data.get("duration", 30) or 30))
        )
        room = data.get("room")
        room = room.get("id") if isinstance(room, dict) else room
        slot = TalkSlot.objects.create(
            schedule=request.event.wip_schedule,
            room=(
                request.event.rooms.get(pk=room)
                if room
                else request.event.rooms.first()
            ),
            description=LazyI18nString(data.get("title")),
            start=start,
            end=end,
        )
        return JsonResponse(serialize_break(slot))


class ScheduleWarnings(EventPermissionRequired, View):
    permission_required = "orga.edit_schedule"

    def get(self, request, event):
        return JsonResponse(
            {
                talk.submission.code: warnings
                for talk, warnings in self.request.event.wip_schedule.get_all_talk_warnings().items()
            }
        )


class ScheduleAvailabilities(EventPermissionRequired, View):
    permission_required = "orga.edit_schedule"

    def get(self, request, event):
        return JsonResponse(
            {
                "talks": self._get_speaker_availabilities(),
                "rooms": self._get_room_availabilities(),
            }
        )

    def _get_room_availabilities(self):
        # Serializing by hand because it's faster and we don't need
        # IDs or allDay
        return {
            room.pk: [
                {
                    "start": av.start.isoformat(),
                    "end": av.end.isoformat(),
                }
                for av in room.availabilities.all()
            ]
            for room in self.request.event.rooms.all().prefetch_related(
                "availabilities"
            )
        }

    def _get_speaker_availabilities(self):
        # Serializing by hand because it's faster and we don't need
        # IDs or allDay
        speaker_avails = collections.defaultdict(list)
        for avail in self.request.event.availabilities.filter(
            person__isnull=False
        ).select_related("person__user"):
            speaker_avails[avail.person.user.pk].append(avail)

        result = {}

        for talk in (
            self.request.event.wip_schedule.talks.filter(submission__isnull=False)
            .select_related("submission")
            .prefetch_related("submission__speakers")
        ):
            if talk.submission.speakers.count() == 1:
                result[talk.id] = [
                    {
                        "start": av.start.isoformat(),
                        "end": av.end.isoformat(),
                    }
                    for av in speaker_avails[talk.submission.speakers.first().pk]
                ]
            else:
                all_speaker_avails = [
                    speaker_avails[speaker.pk]
                    for speaker in talk.submission.speakers.all()
                    if speaker_avails[speaker.pk]
                ]
                if not all_speaker_avails:
                    result[talk.id] = []
                else:
                    result[talk.id] = [
                        {
                            "start": av.start.isoformat(),
                            "end": av.end.isoformat(),
                        }
                        for av in Availability.intersection(*all_speaker_avails)
                    ]
        return result


class TalkUpdate(PermissionRequired, View):
    permission_required = "orga.schedule_talk"

    def get_permission_object(self):
        return self.request.event

    def get_object(self):
        return self.request.event.wip_schedule.talks.filter(
            pk=self.kwargs.get("pk")
        ).first()

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def patch(self, request, event, pk):
        talk = self.get_object()
        if not talk:
            return JsonResponse({"error": "Talk not found"})
        data = json.loads(request.body.decode())
        if data.get("start"):
            duration = talk.duration
            talk.start = dateutil.parser.parse(data.get("start"))
            if data.get("end"):
                talk.end = dateutil.parser.parse(data["end"])
            elif data.get("duration"):
                talk.end = talk.start + dt.timedelta(minutes=int(data["duration"]))
            elif not talk.submission:
                talk.end = talk.start + dt.timedelta(minutes=duration or 30)
            else:
                talk.end = talk.start + dt.timedelta(
                    minutes=talk.submission.get_duration()
                )
            talk.room = request.event.rooms.get(
                pk=data["room"] or getattr(talk.room, "pk", None)
            )
            if not talk.submission:
                new_description = LazyI18nString(data.get("title", ""))
                talk.description = (
                    new_description if str(new_description) else talk.description
                )
            talk.save(update_fields=["start", "end", "room", "description", "updated"])
            talk.refresh_from_db()
        else:
            talk.start = None
            talk.end = None
            talk.room = None
            talk.save(update_fields=["start", "end", "room", "updated"])

        with_speakers = self.request.event.cfp.request_availabilities
        warnings = talk.schedule.get_talk_warnings(talk, with_speakers=with_speakers)

        return JsonResponse(serialize_slot(talk, warnings=warnings))

    def delete(self, request, event, pk):
        talk = self.get_object()
        if not talk:
            return JsonResponse({"error": "Talk not found"})
        if talk.submission:
            return JsonResponse({"error": "Cannot delete talk."})
        talk.delete()
        return JsonResponse({"success": True})


class QuickScheduleView(PermissionRequired, UpdateView):
    permission_required = "orga.schedule_talk"
    form_class = QuickScheduleForm
    template_name = "orga/schedule/quick.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        return kwargs

    def get_object(self):
        return self.request.event.wip_schedule.talks.filter(
            submission__code__iexact=self.kwargs.get("code")
        ).first()

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _("The session has been scheduled."))
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.path


class RoomList(EventPermissionRequired, TemplateView):
    template_name = "orga/schedule/room_list.html"
    permission_required = "orga.change_settings"


class RoomDelete(EventPermissionRequired, View):
    permission_required = "orga.edit_room"
    permission_required = "orga.change_settings"

    def get_object(self):
        return self.request.event.rooms.filter(pk=self.kwargs["pk"]).first()

    def dispatch(self, request, event, pk):
        super().dispatch(request, event, pk)
        try:
            self.get_object().delete()
            messages.success(
                self.request, _("Room deleted. Hopefully nobody was still in there …")
            )
        except ProtectedError:
            messages.error(
                request,
                _(
                    "There is or was a session scheduled in this room. It cannot be deleted."
                ),
            )

        return redirect(request.event.orga_urls.room_settings)


@method_decorator(csp_update(SCRIPT_SRC="'self' 'unsafe-eval'"), name="dispatch")
class RoomDetail(EventPermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = Room
    form_class = RoomForm
    template_name = "orga/schedule/room_form.html"
    permission_required = "orga.view_room"

    @cached_property
    def write_permission_required(self):
        if "pk" not in self.kwargs:
            return "orga.change_settings"
        return "orga.edit_room"

    def get_object(self):
        with suppress(Room.DoesNotExist, KeyError):
            return self.request.event.rooms.get(pk=self.kwargs["pk"])

    @property
    def permission_object(self):
        return self.get_object() or self.request.event

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.room_settings

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        return kwargs

    def form_valid(self, form):
        form.instance.event = self.request.event
        created = not bool(form.instance.pk)
        result = super().form_valid(form)
        messages.success(self.request, _("Saved!"))
        if created:
            form.instance.log_action(
                "pretalx.room.create", person=self.request.user, orga=True
            )
        else:
            form.instance.log_action(
                "pretalx.event.update", person=self.request.user, orga=True
            )
        return result


class RoomOrderView(OrderModelView):
    model = Room
    permission_required = "orga.edit_room"

    def get_success_url(self):
        return self.request.event.orga_urls.room_settings
