import json
import os.path
import xml.etree.ElementTree as ET
from datetime import timedelta

import dateutil.parser
from django.contrib import messages
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, TemplateView, View
from i18nfield.utils import I18nJSONEncoder

from pretalx.agenda.management.commands.export_schedule_html import (
    Command as ExportScheduleHtml,
)
from pretalx.agenda.tasks import export_schedule_html
from pretalx.common.mixins.views import ActionFromUrl, PermissionRequired
from pretalx.common.signals import register_data_exporters
from pretalx.common.views import CreateOrUpdateView
from pretalx.orga.forms.schedule import ScheduleImportForm, ScheduleReleaseForm
from pretalx.orga.views.event import EventSettingsPermission
from pretalx.schedule.forms import RoomForm
from pretalx.schedule.models import Availability, Room


class ScheduleView(PermissionRequired, TemplateView):
    template_name = 'orga/schedule/index.html'
    permission_required = 'orga.view_schedule'

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, event):
        ctx = super().get_context_data()
        version = self.request.GET.get('version')
        ctx['schedule_version'] = version
        ctx['active_schedule'] = self.request.event.schedules.filter(version=version).first() if version else self.request.event.wip_schedule
        ctx['release_form'] = ScheduleReleaseForm()
        return ctx


class ScheduleExportView(PermissionRequired, TemplateView):
    template_name = 'orga/schedule/export.html'
    permission_required = 'orga.view_schedule'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['exporters'] = list(exporter(self.request.event) for _, exporter in register_data_exporters.send(self.request.event))
        return ctx

    def get_permission_object(self):
        return self.request.event


class ScheduleExportTriggerView(PermissionRequired, View):
    permission_required = 'orga.view_schedule'

    def get_permission_object(self):
        return self.request.event

    def post(self, request, event):
        export_schedule_html.apply_async(kwargs={'event_id': self.request.event.id})
        messages.success(self.request, _('A new export is being generated and will be available soon.'))
        return redirect(self.request.event.orga_urls.schedule_export)


class ScheduleExportDownloadView(PermissionRequired, View):
    permission_required = 'orga.view_schedule'

    def get_permission_object(self):
        return self.request.event

    def get(self, request, event):
        zip_path = ExportScheduleHtml.get_output_zip_path(self.request.event)
        zip_name = os.path.basename(zip_path)
        response = FileResponse(open(zip_path, 'rb'), content_type='application/force-download')
        response['Content-Disposition'] = 'attachment; filename=' + zip_name
        return response


class ScheduleReleaseView(PermissionRequired, View):
    form_class = ScheduleReleaseForm
    permission_required = 'orga.release_schedule'

    def get_permission_object(self):
        return self.request.event

    def post(self, request, event):
        form = ScheduleReleaseForm(self.request.POST)
        form.is_valid()
        if self.request.event.schedules.filter(version=form.cleaned_data['version']).exists():
            messages.error(self.request, _('Please use a version number you did not use yet!'))
        else:
            self.request.event.release_schedule(form.cleaned_data['version'], user=request.user)
            messages.success(self.request, _('Nice, your schedule has been released!'))
        return redirect(self.request.event.orga_urls.schedule)


class ScheduleResetView(PermissionRequired, View):
    permission_required = 'orga.edit_schedule'

    def get_permission_object(self):
        return self.request.event

    def dispatch(self, request, event):
        schedule_version = self.request.GET.get('version')
        schedule = self.request.event.schedules.filter(version=schedule_version).first()
        if schedule:
            schedule.unfreeze(user=request.user)
            messages.success(self.request, _('Reset successful – start editing the schedule from your selcted version!'))
        else:
            messages.error(self.request, _('Error retrieving the schedule version to reset to.'))
        return redirect(self.request.event.orga_urls.schedule)


class ScheduleToggleView(PermissionRequired, View):
    permission_required = 'orga.edit_schedule'

    def get_permission_object(self):
        return self.request.event

    def dispatch(self, request, event):
        self.request.event.settings.set('show_schedule', not self.request.event.settings.show_schedule)
        return redirect(self.request.event.orga_urls.schedule)


class RoomListApi(PermissionRequired, View):
    permission_required = 'orga.view_room'

    def get_permission_object(self):
        return self.request.event

    def get(self, request, event):
        return JsonResponse({
            'start': request.event.datetime_from.isoformat(),
            'end': request.event.datetime_to.isoformat(),
            'timezone': request.event.timezone,
            'rooms': [
                {
                    'id': room.pk,
                    'name': str(room.name),
                    'description': room.description,
                    'capacity': room.capacity,
                    'url': room.urls.edit,
                    'availabilities': [avail.serialize() for avail in room.availabilities.all()]
                }
                for room in request.event.rooms.order_by('position')
            ]
        }, encoder=I18nJSONEncoder)


def serialize_slot(slot):
    return {
        'id': slot.pk,
        'title': str(slot.submission.title),
        'speakers': [
            {'name': speaker.name, 'nick': speaker.nick}
            for speaker in slot.submission.speakers.all()
        ],
        'submission_type': str(slot.submission.submission_type.name),
        'state': slot.submission.state,
        'description': str(slot.submission.description),
        'abstract': str(slot.submission.abstract),
        'notes': slot.submission.notes,
        'duration': slot.submission.duration or slot.submission.submission_type.default_duration,
        'content_locale': slot.submission.content_locale,
        'do_not_record': slot.submission.do_not_record,
        'room': slot.room.pk if slot.room else None,
        'start': slot.start.isoformat() if slot.start else None,
        'end': slot.end.isoformat() if slot.end else None,
        'url': slot.submission.orga_urls.base,
    }


class TalkList(PermissionRequired, View):
    permission_required = 'orga.edit_schedule'

    def get_permission_object(self):
        return self.request.event

    def get(self, request, event):
        version = self.request.GET.get('version')
        if version:
            schedule = request.event.schedules.filter(version=version).first()
        else:
            schedule = request.event.wip_schedule

        if not schedule:
            return JsonResponse({'results': []})
        return JsonResponse(
            {'results': [serialize_slot(slot) for slot in schedule.talks.all()]},
            encoder=I18nJSONEncoder
        )


class TalkUpdate(PermissionRequired, View):
    permission_required = 'orga.schedule_talk'

    def get_object(self):
        return self.request.event.wip_schedule.talks.filter(pk=self.kwargs.get('pk')).first()

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


class RoomTalkAvailabilities(PermissionRequired, View):
    permission_required = 'orga.edit_room'

    def get_permission_object(self):
        return self.request.event

    def get(self, request, event, talkid, roomid):
        talk = request.event.wip_schedule.talks.filter(pk=talkid).first()
        room = request.event.rooms.filter(pk=roomid).first()
        if not (talk and room):
            return JsonResponse({'results': []})

        availabilitysets = [
            room.availabilities.all(),
            *[
                speaker.profiles.filter(event=request.event).first().availabilities.all()
                for speaker in talk.submission.speakers.all()
                if speaker.profiles.filter(event=request.event).exists()
            ],
        ]
        availabilities = Availability.intersection(*availabilitysets)

        return JsonResponse({
            'results': [
                avail.serialize() for avail in availabilities
            ],
        })


class ScheduleImportView(PermissionRequired, FormView):
    permission_required = 'orga.release_schedule'
    template_name = 'orga/schedule/import.html'
    form_class = ScheduleImportForm

    def get_permission_object(self):
        return self.request.event

    def get_success_url(self):
        return self.request.event.orga_urls.schedule_import

    def form_valid(self, form):
        from pretalx.schedule.utils import process_frab
        try:
            tree = ET.parse('path')
            root = tree.getroot()
        except Exception as e:
            messages.error(self.request, _('Unable to parse XML file: ') + str(e))
        try:
            with transaction.atomic():
                messages.success(self.request, process_frab(root, self.request.event))
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, _('Unable to release new schedule: ' + str(e)))
        return super().form_invalid(form)


class RoomList(EventSettingsPermission, TemplateView):
    template_name = 'orga/schedule/room_list.html'


class RoomDelete(EventSettingsPermission, View):
    permission_required = 'orga.edit_room'

    def dispatch(self, request, event, pk):
        try:
            request.event.rooms.filter(pk=pk).delete()
            messages.success(self.request, _('Room deleted. Hopefully nobody was still in there …'))
        except ProtectedError:  # TODO: show which/how many talks are concerned
            messages.error(request, _('There is or was a talk scheduled in this room. It cannot be deleted.'))

        return redirect(request.event.orga_urls.room_settings)


class RoomDetail(EventSettingsPermission, ActionFromUrl, CreateOrUpdateView):
    model = Room
    form_class = RoomForm
    template_name = 'orga/schedule/room_form.html'
    permission_required = 'orga.view_room'

    @property
    def write_permission_required(self):
        if 'pk' not in self.kwargs:
            return 'orga.change_settings'
        return 'orga.edit_room'

    def get_object(self):
        try:
            return self.request.event.rooms.get(pk=self.kwargs['pk'])
        except (Room.DoesNotExist, KeyError):
            return

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.room_settings

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super().get_form_kwargs(*args, **kwargs)
        kwargs['event'] = self.request.event
        return kwargs

    def form_valid(self, form):
        form.instance.event = self.request.event
        created = not bool(form.instance.pk)
        ret = super().form_valid(form)
        messages.success(self.request, _('Saved!'))
        if created:
            form.instance.log_action('pretalx.room.create', person=self.request.user, orga=True)
        else:
            form.instance.log_action('pretalx.event.update', person=self.request.user, orga=True)
        return ret
