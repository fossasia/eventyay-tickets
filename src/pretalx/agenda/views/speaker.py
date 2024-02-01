import io
from collections import defaultdict
from urllib.parse import urlparse

import vobject
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import Storage
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.views.decorators.cache import cache_page
from django.views.generic import DetailView, ListView, TemplateView
from django_context_decorator import context

from pretalx.common.mixins.views import (
    EventPermissionRequired,
    Filterable,
    PermissionRequired,
    SocialMediaCardMixin,
)
from pretalx.common.utils import safe_filename
from pretalx.person.models import SpeakerProfile, User
from pretalx.submission.models import QuestionTarget


class SpeakerList(EventPermissionRequired, Filterable, ListView):
    context_object_name = "speakers"
    template_name = "agenda/speakers.html"
    permission_required = "agenda.view_schedule"
    default_filters = ("user__name__icontains",)

    def get_queryset(self):
        qs = (
            SpeakerProfile.objects.filter(
                user__in=self.request.event.speakers, event=self.request.event
            )
            .select_related("user", "event")
            .order_by("user__name")
        )
        qs = self.filter_queryset(qs)

        speaker_mapping = defaultdict(list)
        for talk in self.request.event.talks.all().prefetch_related("speakers"):
            for speaker in talk.speakers.all():
                speaker_mapping[speaker.code].append(talk)

        for profile in qs:
            profile.talks = speaker_mapping[profile.user.code]
        return qs


class SpeakerView(PermissionRequired, TemplateView):
    template_name = "agenda/speaker.html"
    permission_required = "agenda.view_speaker"
    slug_field = "code"

    @context
    @cached_property
    def profile(self):
        return (
            SpeakerProfile.objects.filter(
                event=self.request.event, user__code__iexact=self.kwargs["code"]
            )
            .select_related("user")
            .first()
        )

    @context
    @cached_property
    def talks(self):
        if not self.request.event.current_schedule:
            return []
        return self.request.event.current_schedule.talks.filter(
            submission__speakers__code=self.kwargs["code"], is_visible=True
        )

    def get_permission_object(self):
        return self.profile

    @context
    def answers(self):
        return self.profile.user.answers.filter(
            question__is_public=True,
            question__event=self.request.event,
            question__target=QuestionTarget.SPEAKER,
        ).select_related("question")


class SpeakerRedirect(DetailView):
    model = User

    def dispatch(self, request, **kwargs):
        speaker = self.get_object()
        profile = speaker.profiles.filter(event=self.request.event).first()
        if profile and self.request.user.has_perm("agenda.view_speaker", profile):
            return redirect(profile.urls.public.full())
        raise Http404()


class SpeakerTalksIcalView(PermissionRequired, DetailView):
    context_object_name = "profile"
    permission_required = "agenda.view_speaker"
    slug_field = "code"

    def get_object(self, queryset=None):
        return SpeakerProfile.objects.filter(
            event=self.request.event, user__code__iexact=self.kwargs["code"]
        ).first()

    def get(self, request, event, *args, **kwargs):
        if not self.request.event.current_schedule:
            raise Http404()
        netloc = urlparse(settings.SITE_URL).netloc
        speaker = self.get_object()
        slots = self.request.event.current_schedule.talks.filter(
            submission__speakers=speaker.user, is_visible=True
        ).select_related("room", "submission")

        cal = vobject.iCalendar()
        cal.add("prodid").value = (
            f"-//pretalx//{netloc}//{request.event.slug}//{speaker.code}"
        )

        for slot in slots:
            slot.build_ical(cal)

        try:
            speaker_name = Storage().get_valid_name(
                name=speaker.user.name or speaker.user.code
            )
        except SuspiciousFileOperation:
            speaker_name = Storage().get_valid_name(name=speaker.user.code)
        return HttpResponse(
            cal.serialize(),
            content_type="text/calendar",
            headers={
                "Content-Disposition": f'attachment; filename="{request.event.slug}-{safe_filename(speaker_name)}.ics"'
            },
        )


class SpeakerSocialMediaCard(SocialMediaCardMixin, SpeakerView):
    def get_image(self):
        user = self.profile.user
        if user.avatar:
            return user.avatar


@cache_page(60 * 60)
def empty_avatar_view(request, event):
    # cached for an hour
    color = request.event.primary_color or settings.DEFAULT_EVENT_PRIMARY_COLOR
    avatar_template = f"""<svg
   xmlns="http://www.w3.org/2000/svg"
   viewBox="0 0 100 100">
  <g>
    <path
       id="body"
       d="m 2,98 h 96 0 c 0,0 6,-65 -48,-52 c 0,0 -54,-10 -48,52"
       style="fill:none;stroke:{color};stroke-width:1.6;stroke-linecap:butt;stroke-linejoin:round;stroke-miterlimit:4;stroke-dasharray:2.1, 2.1;stroke-dashoffset:0;stroke-opacity:0.87" />
    <ellipse
       ry="27"
       rx="27"
       cy="28"
       cx="50"
       id="heady"
       style="fill:#ffffff;stroke:{color};stroke-width:1.3;stroke-linecap:butt;stroke-linejoin:round;stroke-miterlimit:4;stroke-dasharray:6.5, 8;stroke-dashoffset:4;stroke-opacity:0.87" />
  </g>
</svg>"""
    return FileResponse(
        io.BytesIO(avatar_template.encode()),
        as_attachment=True,
        content_type="image/svg+xml",
    )
