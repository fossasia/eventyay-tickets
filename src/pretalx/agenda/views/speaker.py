from urllib.parse import urlparse

import vobject
from csp.decorators import csp_update
from django.conf import settings
from django.core.files.storage import Storage
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views.generic import DetailView, TemplateView
from django_context_decorator import context

from pretalx.common.mixins.views import PermissionRequired
from pretalx.person.models import SpeakerProfile, User
from pretalx.submission.models import QuestionTarget


@method_decorator(csp_update(IMG_SRC="https://www.gravatar.com"), name='dispatch')
class SpeakerView(PermissionRequired, TemplateView):
    template_name = 'agenda/speaker.html'
    permission_required = 'agenda.view_speaker'
    slug_field = 'code'

    @context
    @cached_property
    def profile(self):
        return (
            SpeakerProfile.objects.filter(
                event=self.request.event, user__code__iexact=self.kwargs['code']
            )
            .select_related('user')
            .first()
        )

    def get_permission_object(self):
        return self.profile

    @context
    def answers(self):
        return self.profile.user.answers.filter(
            question__is_public=True,
            question__event=self.request.event,
            question__target=QuestionTarget.SPEAKER,
        ).select_related('question')


class SpeakerRedirect(DetailView):
    model = User

    def dispatch(self, request, **kwargs):
        speaker = self.get_object()
        profile = speaker.profiles.filter(event=self.request.event).first()
        if profile and self.request.user.has_perm('agenda.view_speaker', profile):
            return redirect(profile.urls.public.full())
        raise Http404()


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
            submission__speakers=speaker.user, is_visible=True
        ).select_related('room', 'submission')

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
