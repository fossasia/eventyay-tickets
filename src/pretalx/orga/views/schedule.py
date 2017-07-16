import json
from datetime import timedelta

import dateutil.parser
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, TemplateView, View
from i18nfield.utils import I18nJSONEncoder

from pretalx.orga.forms.schedule import ScheduleReleaseForm
from pretalx.schedule.models import TalkSlot


class ScheduleView(TemplateView):
    template_name = 'orga/schedule/index.html'

    def get_context_data(self, event):
        ctx = super().get_context_data()
        ctx['schedule_version'] = self.request.GET.get('version')
        ctx['release_form'] = ScheduleReleaseForm()
        return ctx


class ScheduleReleaseView(View):
    form_class = ScheduleReleaseForm

    def post(self, request, event):
        form = ScheduleReleaseForm(self.request.POST)
        form.is_valid()
        self.request.event.release_schedule(form.cleaned_data['version'], user=request.user)
        messages.success(self.request, _('Nice, your schedule has been released!'))
        return redirect(reverse('orga:schedule.main', kwargs={'event': self.request.event.slug}))

class RoomList(View):

    def get(self, request, event):
        return JsonResponse({
            'start': request.event.datetime_from.isoformat(),
            'end': request.event.datetime_to.isoformat(),
            'timezone': request.event.timezone,
            'rooms': [
                {
                    'id': room.pk,
                    'name': room.name,
                    'description': room.description,
                    'capacity': room.capacity,
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
    }


class TalkList(View):

    def get(self, request, event):
        version = self.request.GET.get('version')
        if version:
            schedule = request.event.schedules.get(version=version)
        else:
            schedule = request.event.wip_schedule

        return JsonResponse(
            {'results': [serialize_slot(slot) for slot in schedule.talks.all()]},
            encoder=I18nJSONEncoder
        )


class TalkUpdate(View):

    def patch(self, request, event, pk):
        try:
            talk = request.event.wip_schedule.talks.get(pk=pk)
        except TalkSlot.DoesNotExist:
            return JsonResponse({})
        data = json.loads(request.body.decode())

        if data.get('start'):
            talk.start = dateutil.parser.parse(data.get('start'))
            talk.end = talk.start + timedelta(minutes=talk.duration)
        else:
            talk.start = None
            talk.end = None

        if data.get('room'):
            talk.room = request.event.rooms.get(pk=data.get('room'))
        else:
            talk.room = None

        talk.save(update_fields=['start', 'end', 'room'])

        return JsonResponse(serialize_slot(talk))
