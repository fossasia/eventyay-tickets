import collections
import datetime as dt
import json
import logging

import dateutil.parser
from celery.exceptions import TaskError
from csp.decorators import csp_update
from django.conf import settings
from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, TemplateView, UpdateView, View
from django_context_decorator import context
from i18nfield.strings import LazyI18nString
from i18nfield.utils import I18nJSONEncoder

from eventyay.agenda.management.commands.export_schedule_html import get_export_zip_path
from eventyay.agenda.tasks import export_schedule_html
from eventyay.agenda.views.utils import get_schedule_exporters
from eventyay.common.language import get_current_language_information
from eventyay.common.text.path import safe_filename
from eventyay.common.text.phrases import phrases
from eventyay.common.views.generic import OrgaCRUDView
from eventyay.common.views.mixins import (
    EventPermissionRequired,
    OrderActionMixin,
    PermissionRequired,
)
from eventyay.orga.forms.schedule import ScheduleExportForm, ScheduleReleaseForm
from eventyay.schedule.forms import QuickScheduleForm, RoomForm
from eventyay.base.models import Availability, Room, TalkSlot

SCRIPT_SRC = "'self' 'unsafe-eval'"
DEFAULT_SRC = "'self'"


if settings.VITE_DEV_MODE:
    SCRIPT_SRC = (f'{SCRIPT_SRC} {settings.VITE_DEV_SERVER}',)
    DEFAULT_SRC = (f'{DEFAULT_SRC} {settings.VITE_DEV_SERVER} {settings.VITE_DEV_SERVER.replace("http", "ws")}',)


logger = logging.getLogger(__name__)


class ScheduleView(EventPermissionRequired, TemplateView):
    template_name = 'orga/schedule/index.html'
    permission_required = 'base.orga_view_schedule'

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        version = self.request.GET.get('version')

        # get current translations language from django
        language_information = get_current_language_information()
        path = language_information.get('path', language_information.get('code'))
        result['gettext_language'] = path.replace('-', '_')

        result['schedule_version'] = version
        result['active_schedule'] = (
            self.request.event.schedules.filter(version=version).first() if version else self.request.event.wip_schedule
        )
        return result


class ScheduleExportView(EventPermissionRequired, FormView):
    template_name = 'orga/schedule/export.html'
    permission_required = 'base.update_event'
    form_class = ScheduleExportForm

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result['event'] = self.request.event
        return result

    @context
    def exporters(self):
        return [exporter for exporter in get_schedule_exporters(self.request) if exporter.group != 'speaker']

    @context
    def tablist(self):
        return {
            'custom': _('CSV/JSON exports'),
            'general': _('More exports'),
            'api': _('API'),
        }

    def form_valid(self, form):
        result = form.export_data()
        if not result:
            messages.success(self.request, _('No data to be exported'))
            return redirect(self.request.path)
        return result


class ScheduleExportTriggerView(EventPermissionRequired, View):
    permission_required = 'base.update_event'

    def post(self, request, event):
        if not settings.CELERY_TASK_ALWAYS_EAGER:
            export_schedule_html.apply_async(kwargs={'event_id': self.request.event.id}, ignore_result=True)
            messages.success(
                self.request,
                _('A new export is being generated and will be available soon.'),
            )
        else:
            self.request.event.cache.set('rebuild_schedule_export', True, None)
            messages.success(
                self.request,
                _(
                    'A new export will be generated on the next scheduled opportunity – please contact your administrator for details.'
                ),
            )

        return redirect(self.request.event.orga_urls.schedule_export)


class ScheduleExportDownloadView(EventPermissionRequired, View):
    permission_required = 'base.update_event'

    def get(self, request, event):
        try:
            zip_path = get_export_zip_path(self.request.event)
            response = FileResponse(open(zip_path, 'rb'), as_attachment=True)
        except Exception as e:
            messages.error(
                request,
                _('Could not find the current export, please try to regenerate it. ({error})').format(error=str(e)),
            )
            return redirect(self.request.event.orga_urls.schedule_export)
        response['Content-Disposition'] = 'attachment; filename=' + safe_filename(zip_path.name)
        return response


class ScheduleReleaseView(EventPermissionRequired, FormView):
    form_class = ScheduleReleaseForm
    permission_required = 'base.release_schedule'
    template_name = 'orga/schedule/release.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['locales'] = self.request.event.locales
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

    def form_invalid(self, form):
        messages.error(self.request, _('You have to provide a new, unique schedule version!'))
        return super().form_invalid(form)

    def form_valid(self, form):
        self.request.event.release_schedule(
            form.cleaned_data['version'],
            user=self.request.user,
            notify_speakers=form.cleaned_data['notify_speakers'],
            comment=form.cleaned_data['comment'],
        )
        messages.success(self.request, _('Nice, your schedule has been released!'))
        return redirect(self.request.event.orga_urls.schedule)


class ScheduleResetView(EventPermissionRequired, View):
    permission_required = 'base.release_schedule'

    def dispatch(self, request, event):
        super().dispatch(request, event)
        schedule_version = self.request.GET.get('version')
        schedule = self.request.event.schedules.filter(version=schedule_version).first()
        if schedule:
            schedule.unfreeze(user=request.user)
            messages.success(
                self.request,
                _('Reset successful – start editing the schedule from your selected version!'),
            )
        else:
            messages.error(self.request, _('Error retrieving the schedule version to reset to.'))
        return redirect(self.request.event.orga_urls.schedule)


class ScheduleToggleView(EventPermissionRequired, View):
    permission_required = 'base.update_event'

    def dispatch(self, request, event):
        super().dispatch(request, event)
        self.request.event.feature_flags['show_schedule'] = not self.request.event.get_feature_flag('show_schedule')
        self.request.event.save()
        # Trigger tickets to hidden/unhidden schedule menu
        try:
            from eventyay.orga.tasks import trigger_public_schedule

            trigger_public_schedule.apply_async(
                kwargs={
                    'is_show_schedule': self.request.event.feature_flags['show_schedule'],
                    'event_slug': self.request.event.slug,
                    'organiser_slug': self.request.event.organiser.slug,
                    'user_email': self.request.user.email,
                },
                ignore_result=True,
            )
        except (TaskError, ConnectionError) as e:
            logger.warning(
                "Unexpected error when trying to trigger schedule's state to external system: %s",
                e,
            )
        except Exception as e:
            logger.error('Unexpected error in task: %s', e)
        return redirect(self.request.event.orga_urls.schedule)


class ScheduleResendMailsView(EventPermissionRequired, View):
    permission_required = 'base.release_schedule'

    def dispatch(self, request, event):
        super().dispatch(request, event)
        if self.request.event.current_schedule:
            mails = self.request.event.current_schedule.generate_notifications(save=True)
            messages.success(
                self.request,
                phrases.orga.mails_in_outbox.format(count=len(mails)),
            )
        else:
            messages.warning(
                self.request,
                _('You can only regenerate mails after the first schedule was released.'),
            )
        return redirect(self.request.event.orga_urls.schedule)


def serialize_break(slot):
    return {
        'id': slot.pk,
        'title': slot.description.data if slot.description else '',
        'description': '',
        'room': slot.room.pk if slot.room else None,
        'start': slot.start.isoformat() if slot.start else None,
        'end': slot.end.isoformat() if slot.end else None,
        'duration': slot.duration,
        'updated': slot.updated.isoformat(),
    }


def serialize_slot(slot, warnings=None):
    base_data = serialize_break(slot)
    if slot.submission:
        speakers_list = [
            {'name': getattr(speaker, 'name', None) or getattr(speaker, 'get_display_name', lambda: str(speaker))()}
            for speaker in slot.submission.speakers.all()
        ]
        submission_data = {
            'id': slot.pk,
            'title': str(slot.submission.title),
            'speakers': speakers_list,
            'submission_type': str(slot.submission.submission_type.name),
            'track': (
                {
                    'name': str(slot.submission.track.name),
                    'color': slot.submission.track.color,
                }
                if slot.submission.track
                else None
            ),
            'state': slot.submission.state,
            'description': str(slot.submission.description),
            'abstract': str(slot.submission.abstract),
            'notes': slot.submission.notes,
            'duration': slot.submission.duration or slot.submission.submission_type.default_duration,
            'content_locale': slot.submission.content_locale,
            'do_not_record': slot.submission.do_not_record,
            'room': slot.room.pk if slot.room else None,
            'start': slot.local_start.isoformat() if slot.start else None,
            'end': slot.local_end.isoformat() if slot.end else None,
            'url': slot.submission.orga_urls.base,
            'warnings': warnings or [],
        }
        return {**base_data, **submission_data}
    return base_data


class TalkList(EventPermissionRequired, View):
    permission_required = 'base.release_schedule'

    def get(self, request, event):
        version = self.request.GET.get('version')
        schedule = None
        if version:
            schedule = request.event.schedules.filter(version=version).first()
        if not schedule:
            schedule = request.event.wip_schedule

        filter_updated = request.GET.get('since')
        result = schedule.build_data(
            all_talks=True,
            all_rooms=not bool(filter_updated),
            filter_updated=filter_updated,
        )

        if request.GET.get('warnings'):
            result['warnings'] = {
                talk.submission.code: warnings
                for talk, warnings in schedule.get_all_talk_warnings(filter_updated=filter_updated).items()
            }
        result['now'] = now().strftime('%Y-%m-%d %H:%M:%S%z')
        result['locales'] = request.event.locales
        return JsonResponse(result, encoder=I18nJSONEncoder)

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, event):
        data = json.loads(request.body.decode())
        start = dateutil.parser.parse(data.get('start')) if data.get('start') else request.event.datetime_from
        end = (
            dateutil.parser.parse(data.get('end'))
            if data.get('end')
            else start + dt.timedelta(minutes=int(data.get('duration', 30) or 30))
        )
        room = data.get('room')
        room = room.get('id') if isinstance(room, dict) else room
        slot = TalkSlot.objects.create(
            schedule=request.event.wip_schedule,
            room=(request.event.rooms.get(pk=room) if room else request.event.rooms.first()),
            description=LazyI18nString(data.get('title')),
            start=start,
            end=end,
        )
        return JsonResponse(serialize_break(slot))


class ScheduleWarnings(EventPermissionRequired, View):
    permission_required = 'base.release_schedule'

    def get(self, request, event):
        return JsonResponse(
            {
                talk.submission.code: warnings
                for talk, warnings in self.request.event.wip_schedule.get_all_talk_warnings().items()
            }
        )


class ScheduleAvailabilities(EventPermissionRequired, View):
    permission_required = 'base.release_schedule'

    def get(self, request, event):
        return JsonResponse(
            {
                'talks': self._get_speaker_availabilities(),
                'rooms': self._get_room_availabilities(),
            }
        )

    def _get_room_availabilities(self):
        # Serializing by hand because it's faster and we don't need
        # IDs or allDay
        return {
            room.pk: [av.serialize(full=False) for av in room.availabilities.all()]
            for room in self.request.event.rooms.all().prefetch_related('availabilities')
        }

    def _get_speaker_availabilities(self):
        # Serializing by hand because it's faster and we don't need
        # IDs or allDay
        speaker_avails = collections.defaultdict(list)
        for avail in self.request.event.availabilities.filter(person__isnull=False).select_related('person__user'):
            speaker_avails[avail.person.user.pk].append(avail)

        result = {}

        for talk in (
            self.request.event.wip_schedule.talks.filter(submission__isnull=False)
            .select_related('submission')
            .prefetch_related('submission__speakers')
        ):
            if talk.submission.speakers.count() == 1:
                result[talk.id] = [
                    av.serialize(full=False) for av in speaker_avails[talk.submission.speakers.first().pk]
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
                        av.serialize(full=False) for av in Availability.intersection(*all_speaker_avails)
                    ]
        return result


class TalkUpdate(PermissionRequired, View):
    permission_required = 'base.update_talkslot'

    def get_object(self):
        return self.request.event.wip_schedule.talks.filter(pk=self.kwargs.get('pk')).first()

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def patch(self, request, event, pk):
        talk = self.get_object()
        if not talk:
            return JsonResponse({'error': 'Talk not found'})
        data = json.loads(request.body.decode())
        if data.get('start'):
            duration = talk.duration
            talk.start = dateutil.parser.parse(data.get('start'))
            if data.get('end'):
                talk.end = dateutil.parser.parse(data['end'])
            elif data.get('duration'):
                talk.end = talk.start + dt.timedelta(minutes=int(data['duration']))
            elif not talk.submission:
                talk.end = talk.start + dt.timedelta(minutes=duration or 30)
            else:
                talk.end = talk.start + dt.timedelta(minutes=talk.submission.get_duration())
            talk.room = request.event.rooms.get(pk=data['room'] or getattr(talk.room, 'pk', None))
            if not talk.submission:
                new_description = LazyI18nString(data.get('title', ''))
                talk.description = new_description if str(new_description) else talk.description
            talk.save(update_fields=['start', 'end', 'room', 'description', 'updated'])
            talk.refresh_from_db()
        else:
            talk.start = None
            talk.end = None
            talk.room = None
            talk.save(update_fields=['start', 'end', 'room', 'updated'])

        with_speakers = self.request.event.cfp.request_availabilities
        warnings = talk.schedule.get_talk_warnings(talk, with_speakers=with_speakers)

        return JsonResponse(serialize_slot(talk, warnings=warnings))

    def delete(self, request, event, pk):
        talk = self.get_object()
        if not talk:
            return JsonResponse({'error': 'Talk not found'})
        if talk.submission:
            return JsonResponse({'error': 'Cannot delete talk.'})
        talk.delete()
        return JsonResponse({'success': True})


class QuickScheduleView(PermissionRequired, UpdateView):
    permission_required = 'base.update_talkslot'
    form_class = QuickScheduleForm
    template_name = 'orga/schedule/quick.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    def get_object(self):
        return self.request.event.wip_schedule.talks.filter(submission__code__iexact=self.kwargs.get('code')).first()

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('The session has been scheduled.'))
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.path


class RoomView(OrderActionMixin, OrgaCRUDView):
    model = Room
    form_class = RoomForm
    template_namespace = 'orga/schedule'

    def get_queryset(self):
        return self.request.event.rooms.all()

    def get_permission_required(self):
        permission_map = {'list': 'orga_list', 'detail': 'orga_detail'}
        permission = permission_map.get(self.action, self.action)
        return self.model.get_perm(permission)

    def get_generic_title(self, instance=None):
        if instance:
            return _('Room') + f' {phrases.base.quotation_open}{instance.name}{phrases.base.quotation_close}'
        if self.action == 'create':
            return _('New room')
        return _('Rooms')

    def delete_handler(self, request, *args, **kwargs):
        try:
            return super().delete_handler(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                _('There is or was a session scheduled in this room. It cannot be deleted.'),
            )
            return self.delete_view(request, *args, **kwargs)
