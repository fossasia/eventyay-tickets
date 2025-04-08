import datetime as dt
from urllib.parse import unquote, urlparse

import jwt
import requests
import vobject
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView, View
from django_context_decorator import context

from pretalx.agenda.signals import register_recording_provider
from pretalx.agenda.views.utils import encode_email
from pretalx.cfp.views.event import EventPageMixin
from pretalx.common.text.phrases import phrases
from pretalx.common.views.mixins import (
    EventPermissionRequired,
    PermissionRequired,
    SocialMediaCardMixin,
)
from pretalx.schedule.models import Schedule, TalkSlot
from pretalx.submission.forms import FeedbackForm
from pretalx.submission.models import QuestionTarget, Submission, SubmissionStates


class TalkMixin(PermissionRequired):
    permission_required = "agenda.view_submission"

    def get_queryset(self):
        return self.request.event.submissions.prefetch_related(
            "slots",
            "answers",
            "resources",
            "slots__room",
            "speakers",
        ).select_related("submission_type")

    @cached_property
    def object(self):
        return get_object_or_404(
            self.get_queryset(),
            code__iexact=self.kwargs["slug"],
        )

    @context
    @cached_property
    def submission(self):
        return self.object

    def get_permission_object(self):
        return self.submission


class TalkView(TalkMixin, TemplateView):
    template_name = "agenda/talk.html"

    def get_contrast_color(self, bg_color):
        if not bg_color:
            return ""
        bg_color = bg_color.lstrip("#")
        r = int(bg_color[0:2], 16)
        g = int(bg_color[2:4], 16)
        b = int(bg_color[4:6], 16)
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        return "black" if brightness > 128 else "white"

    @cached_property
    def recording(self):
        for __, response in register_recording_provider.send_robust(self.request.event):
            if (
                response
                and not isinstance(response, Exception)
                and getattr(response, "get_recording", None)
            ):
                recording = response.get_recording(self.submission)
                if recording and recording["iframe"]:
                    return recording
        return {}

    @context
    def recording_iframe(self):
        return self.recording.get("iframe")

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        csp_update = {}
        if self.recording.get("csp_header"):
            csp_update["frame-src"] = self.recording.get("csp_header")
        response._csp_update = csp_update
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = TalkSlot.objects.none()
        schedule = Schedule.objects.none()
        if self.request.event.current_schedule:
            schedule = self.request.event.current_schedule
            qs = schedule.talks.filter(is_visible=True).select_related("room")
        elif self.request.user.has_perm("orga.view_schedule", self.request.event):
            schedule = self.request.event.wip_schedule
            qs = schedule.talks.filter(room__isnull=False).select_related("room")
        ctx["talk_slots"] = (
            qs.filter(submission=self.submission)
            .order_by("start")
            .select_related("room")
        )
        ctx["submission_tags"] = self.submission.tags.all()
        for tag_item in ctx["submission_tags"]:
            tag_item.contrast_color = self.get_contrast_color(tag_item.color)
        result = []
        other_slots = (
            schedule.talks.exclude(submission_id=self.submission.pk).filter(
                is_visible=True
            )
            if schedule
            else TalkSlot.objects.none()
        )
        for speaker in self.submission.speakers.all():
            speaker.talk_profile = speaker.event_profile(event=self.request.event)
            speaker.other_submissions = self.request.event.submissions.filter(
                slots__in=other_slots, speakers__in=[speaker]
            ).select_related("event")
            result.append(speaker)
        ctx["speakers"] = result
        return ctx

    @context
    @cached_property
    def submission_description(self):
        return (
            self.submission.abstract
            or self.submission.description
            or _("The session “{title}” at {event}").format(
                title=self.submission.title, event=self.request.event.name
            )
        )

    @context
    @cached_property
    def answers(self):
        return self.submission.answers.filter(
            question__is_public=True,
            question__event=self.request.event,
            question__target=QuestionTarget.SUBMISSION,
        ).select_related("question")


class TalkReviewView(TalkView):
    template_name = "agenda/talk.html"

    def has_permission(self):
        return self.request.event.get_feature_flag("submission_public_review")

    @cached_property
    def object(self):
        return get_object_or_404(
            Submission.all_objects.filter(event=self.request.event),
            review_code=self.kwargs["slug"],
            state__in=[
                SubmissionStates.SUBMITTED,
                SubmissionStates.DRAFT,
                SubmissionStates.ACCEPTED,
                SubmissionStates.CONFIRMED,
            ],
        )

    @context
    def hide_visibility_warning(self):
        return True

    @context
    def hide_speaker_links(self):
        return True


class SingleICalView(EventPageMixin, TalkMixin, View):

    def get(self, request, event, **kwargs):
        code = self.submission.code
        talk_slots = self.submission.slots.filter(
            schedule=self.request.event.current_schedule, is_visible=True
        )

        netloc = urlparse(settings.SITE_URL).netloc
        cal = vobject.iCalendar()
        cal.add("prodid").value = f"-//pretalx//{netloc}//{code}"
        for talk in talk_slots:
            talk.build_ical(cal)
        return HttpResponse(
            cal.serialize(),
            content_type="text/calendar",
            headers={
                "Content-Disposition": f'attachment; filename="{request.event.slug}-{code}.ics"'
            },
        )


class FeedbackView(TalkMixin, FormView):
    form_class = FeedbackForm
    permission_required = "agenda.view_feedback_page"

    def get_queryset(self):
        return self.request.event.submissions.prefetch_related(
            "slots",
            "feedback",
        ).select_related("submission_type")

    @context
    @cached_property
    def talk(self):
        return self.submission

    @context
    @cached_property
    def can_give_feedback(self):
        return self.request.user.has_perm("agenda.give_feedback", self.talk)

    @context
    @cached_property
    def speakers(self):
        return self.talk.speakers.all()

    @cached_property
    def is_speaker(self):
        return self.request.user in self.speakers

    @cached_property
    def template_name(self):
        if self.is_speaker:
            return "agenda/feedback.html"
        return "agenda/feedback_form.html"

    @context
    @cached_property
    def feedback(self):
        if not self.is_speaker:
            return
        return self.talk.feedback.filter(
            Q(speaker=self.request.user) | Q(speaker__isnull=True)
        ).select_related("speaker")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["talk"] = self.talk
        return kwargs

    def form_valid(self, form):
        if not self.can_give_feedback:
            return super().form_invalid(form)
        result = super().form_valid(form)
        form.save()
        messages.success(self.request, phrases.agenda.feedback_success)
        return result

    def get_success_url(self):
        return self.submission.urls.public


class TalkSocialMediaCard(SocialMediaCardMixin, TalkView):
    def get_image(self):
        return self.submission.image


class OnlineVideoJoin(EventPermissionRequired, View):
    permission_required = "agenda.view_schedule"

    def get(self, request, *args, **kwargs):
        # First check video is configured or not
        if (
            "pretalx_venueless" not in request.event.plugin_list
            or not request.event.venueless_settings
            or not request.event.venueless_settings.join_url
            or not request.event.venueless_settings.secret
            or not request.event.venueless_settings.issuer
            or not request.event.venueless_settings.audience
        ):
            return HttpResponse(status=403, content="missing_configuration")

        if not request.user.is_authenticated:
            # redirect to login page if user not logged in yet
            return HttpResponse(status=403, content="user_not_allowed")

        # prepare event data to check from ticket
        if "ticket_link" not in request.event.display_settings:
            return HttpResponse(status=403, content="missing_configuration")

        base_url, organizer, event = self.retrieve_info_from_url(
            request.event.display_settings["ticket_link"]
        )

        if not organizer or not event or not base_url:
            return HttpResponse(status=403, content="missing_configuration")

        check_payload = {"user_email": request.user.email}

        # call to ticket to check if user order ticket yet or not
        response = requests.post(
            f"{base_url}/api/v1/{organizer}/{event}/ticket-check", json=check_payload
        )

        if response.status_code != 200:
            return HttpResponse(status=403, content="user_not_allowed")

        else:
            # Redirect user to online event
            iat = dt.datetime.utcnow()
            exp = iat + dt.timedelta(days=30)
            profile = {
                "display_name": request.user.name,
                "fields": {
                    "pretalx_id": request.user.code,
                },
            }
            if request.user.avatar_url:
                profile["profile_picture"] = request.user.get_avatar_url(request.event)

            payload = {
                "iss": request.event.venueless_settings.issuer,
                "aud": request.event.venueless_settings.audience,
                "exp": exp,
                "iat": iat,
                "uid": encode_email(request.user.email),
                "profile": profile,
                "traits": list(
                    {
                        f"eventyay-video-event-{request.event.slug}",
                    }
                ),
            }
            token = jwt.encode(
                payload, request.event.venueless_settings.secret, algorithm="HS256"
            )

            return JsonResponse(
                {
                    "redirect_url": "{}/#token={}".format(
                        request.event.venueless_settings.join_url, token
                    ).replace("//#", "/#")
                },
                status=200,
            )

    def retrieve_info_from_url(self, url):
        parsed_url = urlparse(url)
        ticket_host = settings.EVENTYAY_TICKET_BASE_PATH
        path = parsed_url.path
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            organizer, event = parts[-2:]
            return ticket_host, unquote(organizer), unquote(event)
        else:
            return ticket_host, None, None
