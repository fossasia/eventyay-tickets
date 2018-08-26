from urllib.parse import urlparse

import vobject
from csp.decorators import csp_update
from django.conf import settings
from django.core.files.storage import Storage
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import DetailView

from pretalx.common.mixins.views import PermissionRequired
from pretalx.person.models import SpeakerProfile


@method_decorator(csp_update(IMG_SRC="https://www.gravatar.com"), name='dispatch')
class SpeakerView(PermissionRequired, DetailView):
    template_name = 'agenda/speaker.html'
    context_object_name = 'profile'
    permission_required = 'agenda.view_speaker'
    slug_field = 'code'

    def get_object(self, queryset=None):
        return SpeakerProfile.objects.filter(
            event=self.request.event, user__code__iexact=self.kwargs['code']
        ).first()

    def get_context_data(self, **kwargs):
        obj = kwargs.get('object')
        context = super().get_context_data(**kwargs)
        context['speaker'] = obj.user
        context['talks'] = obj.talks
        return context


class SpeakerTalksIcalView(PermissionRequired, DetailView):
    context_object_name = 'profile'
    permission_required = 'agenda.view_speaker'
    slug_field = 'code'

    def get_object(self, queryset=None):
        return SpeakerProfile.objects.filter(
            event=self.request.event, user__code__iexact=self.kwargs['code']
        ).first()

    def get(self, request, event, *args, **kwargs):
        netloc = urlparse(settings.SITE_URL).netloc
        speaker = self.get_object()
        slots = self.request.event.current_schedule.talks.filter(
            submission__speakers=speaker.user
        )

        cal = vobject.iCalendar()
        cal.add(
            'prodid'
        ).value = f'-//pretalx//{netloc}//{request.event.slug}//{speaker.code}'

        for slot in slots:
            slot.build_ical(cal)

        resp = HttpResponse(cal.serialize(), content_type='text/calendar')
        speaker_name = Storage().get_valid_name(name=speaker.user.name)
        resp[
            'Content-Disposition'
        ] = f'attachment; filename="{request.event.slug}-{speaker_name}.ics"'
        return resp
