import json
from contextlib import suppress
from datetime import timedelta

import dateutil.parser
from csp.decorators import csp_update
from django.conf import settings
from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView, UpdateView, View
from django_context_decorator import context
from i18nfield.utils import I18nJSONEncoder

from pretalx.agenda.management.commands.export_schedule_html import get_export_zip_path
from pretalx.agenda.tasks import export_schedule_html
from pretalx.api.serializers.room import AvailabilitySerializer
from pretalx.common.mixins.views import (
    ActionFromUrl, EventPermissionRequired, PermissionRequired,
)
from pretalx.common.signals import register_data_exporters
from pretalx.common.views import CreateOrUpdateView
from pretalx.orga.forms.schedule import ScheduleReleaseForm
from pretalx.schedule.forms import QuickScheduleForm, RoomForm
from pretalx.schedule.models import Availability, Room
from pretalx.schedule.utils import guess_schedule_version


@method_decorator(csp_update(SCRIPT_SRC="'self' 'unsafe-eval'"), name='dispatch')
class ScheduleView(EventPermissionRequired, TemplateView):
    template_name = 'orga/schedule/index.html'
    permission_required = 'orga.view_schedule'

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        version = self.request.GET.get('version')
        result['schedule_version'] = version
        result['active_schedule'] = (
            self.request.event.schedules.filter(version=version).first()
            if version
            else self.request.event.wip_schedule
        )
        return result


class ScheduleExportView(EventPermissionRequired, TemplateView):
    template_name = 'orga/schedule/export.html'
    permission_required = 'orga.view_schedule'

    @context
    def exporters(self):
        return list(
            exporter(self.request.event)
            for _, exporter in register_data_exporters.send(self.request.event)
        )


class ScheduleExportTriggerView(EventPermissionRequired, View):
    permission_required = 'orga.view_schedule'

    def post(self, request, event):
        if settings.HAS_CELERY:
            export_schedule_html.apply_async(kwargs={'event_id': self.request.event.id})
            messages.success(
                self.request,
                _('A new export is being generated and will be available soon.'),
            )
        else:
            self.request.event.cache.set('rebuild_schedule_export', True, None)
            messages.success(
                self.request,
                _('A new export will be generated on the next scheduled opportunity – please contact your administrator for details.'),
            )

        return redirect(self.request.event.orga_urls.schedule_export)


class ScheduleExportDownloadView(EventPermissionRequired, View):
    permission_required = 'orga.view_schedule'

    def get(self, request, event):
        try:
            zip_path = get_export_zip_path(self.request.event)
            response = FileResponse(open(zip_path, 'rb'), as_attachment=True)
        except Exception as e:
            messages.error(
                request,
                _(
                    'Could not find the current export, please try to regenerate it. ({error})'
                ).format(error=str(e)),
            )
            return redirect(self.request.event.orga_urls.schedule_export)
        response['Content-Disposition'] = 'attachment; filename=' + zip_path.name
        return response


class ScheduleReleaseView(EventPermissionRequired, FormView):
    form_class = ScheduleReleaseForm
    permission_required = 'orga.release_schedule'
    template_name = 'orga/schedule/release.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    @context
    def warnings(self):
        return self.request.event.wip_schedule.warnings

    @context
    def changes(self):
        return self.request.event.wip_schedule.changes

    @context
    def notifications(self):
        return len(self.request.event.wip_schedule.notifications)

    @context
    def suggested_version(self):
        return guess_schedule_version(self.request.event)

    def form_invalid(self, form):
        messages.error(
            self.request, _('You have to provide a new, unique schedule version!')
        )
        return redirect(self.request.event.orga_urls.release_schedule)

    def form_valid(self, form):
        self.request.event.release_schedule(
            form.cleaned_data['version'],
            user=self.request.user,
            notify_speakers=form.cleaned_data['notify_speakers'],
        )
        messages.success(self.request, _('Nice, your schedule has been released!'))
        return redirect(self.request.event.orga_urls.schedule)


class ScheduleResetView(EventPermissionRequired, View):
    permission_required = 'orga.edit_schedule'

    def dispatch(self, request, event):
        super().dispatch(request, event)
        schedule_version = self.request.GET.get('version')
        schedule = self.request.event.schedules.filter(version=schedule_version).first()
        if schedule:
            schedule.unfreeze(user=request.user)
            messages.success(
                self.request,
                _(
                    'Reset successful – start editing the schedule from your selected version!'
                ),
            )
        else:
            messages.error(
                self.request, _('Error retrieving the schedule version to reset to.')
            )
        return redirect(self.request.event.orga_urls.schedule)


class ScheduleToggleView(EventPermissionRequired, View):
    permission_required = 'orga.edit_schedule'

    def dispatch(self, request, event):
        super().dispatch(request, event)
        self.request.event.settings.set(
            'show_schedule', not self.request.event.settings.show_schedule
        )
        return redirect(self.request.event.orga_urls.schedule)


class ScheduleResendMailsView(EventPermissionRequired, View):
    permission_required = 'orga.edit_schedule'

    def dispatch(self, request, event):
        super().dispatch(request, event)
        if self.request.event.current_schedule:
            self.request.event.current_schedule.notify_speakers()
            messages.success(
                self.request,
                _('{count} emails have been saved to the outbox – you can make individual changes there or just send them all.').format(
                    count=len(self.request.event.current_schedule.notifications)
                )
            )
        else:
            messages.warning(self.request, _('You can only regenerate mails after the first schedule was released.'))
        return redirect(self.request.event.orga_urls.schedule)


def serialize_slot(slot):
    return {
        'id': slot.pk,
        'title': str(slot.submission.title),
        'speakers': [
            {'name': speaker.name} for speaker in slot.submission.speakers.all()
        ],
        'submission_type': str(slot.submission.submission_type.name),
        'track': {'name': str(slot.submission.track.name), 'color': slot.submission.track.color} if slot.submission.track else None,
        'state': slot.submission.state,
        'description': str(slot.submission.description),
        'abstract': str(slot.submission.abstract),
        'notes': slot.submission.notes,
        'duration': slot.submission.duration
        or slot.submission.submission_type.default_duration,
        'content_locale': slot.submission.content_locale,
        'do_not_record': slot.submission.do_not_record,
        'room': slot.room.pk if slot.room else None,
        'start': slot.start.isoformat() if slot.start else None,
        'end': slot.end.isoformat() if slot.end else None,
        'url': slot.submission.orga_urls.base,
        'warnings': slot.warnings,
    }


class TalkList(EventPermissionRequired, View):
    permission_required = 'orga.edit_schedule'

    def get(self, request, event):
        result = {
            'start': request.event.datetime_from.isoformat(),
            'end': request.event.datetime_to.isoformat(),
            'timezone': request.event.timezone,
            'results': [],
        }
        version = self.request.GET.get('version')
        if version:
            schedule = request.event.schedules.filter(version=version).first()
        else:
            schedule = request.event.wip_schedule

        if not schedule:
            return JsonResponse(result)
        result['results'] = [
            serialize_slot(slot)
            for slot
            in (
                schedule.talks.all()
                .select_related('submission', 'submission__event', 'room', 'submission__submission_type', 'submission__track')
                .prefetch_related('submission__speakers')
            )
        ]
        return JsonResponse(result, encoder=I18nJSONEncoder)


class TalkUpdate(PermissionRequired, View):
    permission_required = 'orga.schedule_talk'

    def get_object(self):
        return self.request.event.wip_schedule.talks.filter(
            pk=self.kwargs.get('pk')
        ).first()

    def patch(self, request, event, pk):
        talk = self.get_object()
        if not talk:
            return JsonResponse({'error': 'Talk not found'})
        data = json.loads(request.body.decode())

        if data.get('start'):
            talk.start = dateutil.parser.parse(data.get('start'))
            talk.end = talk.start + timedelta(minutes=talk.submission.get_duration())
        else:
            talk.start = None
            talk.end = None

        if data.get('room'):
            talk.room = request.event.rooms.get(pk=data.get('room'))
        else:
            talk.room = None

        talk.save(update_fields=['start', 'end', 'room'])

        return JsonResponse(serialize_slot(talk))


class QuickScheduleView(PermissionRequired, UpdateView):
    permission_required = 'orga.schedule_talk'
    form_class = QuickScheduleForm
    template_name = 'orga/schedule/quick.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    def get_object(self):
        return self.request.event.wip_schedule.talks.filter(
            submission__code__iexact=self.kwargs.get('code')
        ).first()

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('The talk has been scheduled.'))
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.path


class RoomTalkAvailabilities(EventPermissionRequired, View):
    permission_required = 'orga.edit_room'

    def get(self, request, event, talkid, roomid):
        talk = request.event.wip_schedule.talks.filter(pk=talkid).first()
        room = request.event.rooms.filter(pk=roomid).first()
        if not (talk and room):
            return JsonResponse({'results': []})
        if talk.submission.availabilities:
            availabilitysets = [
                room.availabilities.all(),
                talk.submission.availabilities,
            ]
            availabilities = Availability.intersection(*availabilitysets)
        else:
            availabilities = room.availabilities.all()
        return JsonResponse(
            {'results': AvailabilitySerializer(availabilities, many=True).data}
        )


class RoomList(EventPermissionRequired, TemplateView):
    template_name = 'orga/schedule/room_list.html'
    permission_required = 'orga.change_settings'


class RoomDelete(EventPermissionRequired, View):
    permission_required = 'orga.edit_room'
    permission_required = 'orga.change_settings'

    def get_object(self):
        return self.request.event.rooms.filter(pk=self.kwargs['pk']).first()

    def dispatch(self, request, event, pk):
        super().dispatch(request, event, pk)
        try:
            self.get_object().delete()
            messages.success(
                self.request, _('Room deleted. Hopefully nobody was still in there …')
            )
        except ProtectedError:  # TODO: show which/how many talks are concerned
            messages.error(
                request,
                _(
                    'There is or was a talk scheduled in this room. It cannot be deleted.'
                ),
            )

        return redirect(request.event.orga_urls.room_settings)


class RoomDetail(EventPermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = Room
    form_class = RoomForm
    template_name = 'orga/schedule/room_form.html'
    permission_required = 'orga.view_room'

    @cached_property
    def write_permission_required(self):
        if 'pk' not in self.kwargs:
            return 'orga.change_settings'
        return 'orga.edit_room'

    def get_object(self):
        with suppress(Room.DoesNotExist, KeyError):
            return self.request.event.rooms.get(pk=self.kwargs['pk'])

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.room_settings

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    def form_valid(self, form):
        form.instance.event = self.request.event
        created = not bool(form.instance.pk)
        result = super().form_valid(form)
        messages.success(self.request, _('Saved!'))
        if created:
            form.instance.log_action(
                'pretalx.room.create', person=self.request.user, orga=True
            )
        else:
            form.instance.log_action(
                'pretalx.event.update', person=self.request.user, orga=True
            )
        return result


def room_move(request, pk, up=True):
    try:
        room = request.event.rooms.get(pk=pk)
    except Room.DoesNotExist:
        raise Http404(_('The selected room does not exist.'))
    if not request.user.has_perm('orga.edit_room', room):
        messages.error(request, _('Sorry, you are not allowed to reorder rooms.'))
        return
    rooms = list(request.event.rooms.order_by('position'))

    index = rooms.index(room)
    if index != 0 and up:
        rooms[index - 1], rooms[index] = rooms[index], rooms[index - 1]
    elif index != len(rooms) - 1 and not up:
        rooms[index + 1], rooms[index] = rooms[index], rooms[index + 1]

    for i, qt in enumerate(rooms):
        if qt.position != i:
            qt.position = i
            qt.save()
    messages.success(request, _('The order of rooms has been updated.'))


def room_move_up(request, event, pk):
    room_move(request, pk, up=True)
    return redirect(request.event.orga_urls.room_settings)


def room_move_down(request, event, pk):
    room_move(request, pk, up=False)
    return redirect(request.event.orga_urls.room_settings)
