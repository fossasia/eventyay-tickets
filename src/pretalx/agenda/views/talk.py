from urllib.parse import urlparse

import vobject
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView, FormView, ListView, TemplateView
from django_context_decorator import context

from pretalx.agenda.signals import register_recording_provider
from pretalx.cfp.views.event import EventPageMixin
from pretalx.common.mixins.views import (
    EventPermissionRequired, Filterable, PermissionRequired,
)
from pretalx.common.phrases import phrases
from pretalx.person.models.profile import SpeakerProfile
from pretalx.schedule.models import Schedule, TalkSlot
from pretalx.submission.forms import FeedbackForm
from pretalx.submission.models import QuestionTarget, Submission, SubmissionStates


class TalkList(EventPermissionRequired, Filterable, ListView):
    context_object_name = 'talks'
    model = Submission
    template_name = 'agenda/talks.html'
    permission_required = 'agenda.view_schedule'
    default_filters = ('speakers__name__icontains', 'title__icontains')

    def get_queryset(self):
        return self.filter_queryset(self.request.event.talks).select_related('event').prefetch_related('speakers').distinct()

    @context
    def search(self):
        return self.request.GET.get('q')


class SpeakerList(EventPermissionRequired, Filterable, ListView):
    context_object_name = 'speakers'
    template_name = 'agenda/speakers.html'
    permission_required = 'agenda.view_schedule'
    default_filters = ('user__name__icontains',)

    def get_queryset(self):
        qs = SpeakerProfile.objects.filter(
            user__in=self.request.event.speakers, event=self.request.event
        ).select_related('user', 'event').order_by('user__name')
        qs = self.filter_queryset(qs)
        all_talks = list(self.request.event.talks.all().prefetch_related('speakers'))
        for profile in qs:
            profile.talks = [
                talk for talk in all_talks if profile.user in talk.speakers.all()
            ]
        return qs

    @context
    def search(self):
        return self.request.GET.get('q')


class TalkView(PermissionRequired, TemplateView):
    model = Submission
    slug_field = 'code'
    template_name = 'agenda/talk.html'
    permission_required = 'agenda.view_slot'

    def get_object(self, queryset=None):
        talk = self.request.event.talks.prefetch_related('slots', 'answers', 'resources').filter(
            code__iexact=self.kwargs['slug'],
        ).first()
        if talk:
            return talk
        if getattr(self.request, 'is_orga', False):
            talk = self.request.event.submissions.filter(
                code__iexact=self.kwargs['slug'],
            ).prefetch_related('speakers', 'slots', 'answers', 'resources').select_related('submission_type').first()
            if talk:
                return talk
        raise Http404()

    @context
    @cached_property
    def submission(self):
        return self.get_object()

    def get_permission_object(self):
        return self.submission

    @cached_property
    def recording(self):
        for receiver, response in register_recording_provider.send_robust(
            self.request.event
        ):
            if (
                response
                and not isinstance(response, Exception)
                and hasattr(response, 'get_recording')
            ):
                recording = response.get_recording(self.submission)
                if recording and recording['iframe']:
                    return recording
        return {}

    @context
    def recording_iframe(self):
        return self.recording.get('iframe')

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        if self.recording.get('csp_header'):
            response._csp_update = {'child-src': self.recording.get('csp_header')}
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = TalkSlot.objects.none()
        schedule = Schedule.objects.none()
        if self.request.event.current_schedule:
            schedule = self.request.event.current_schedule
            qs = schedule.talks.filter(is_visible=True).select_related('room')
        elif self.request.is_orga:
            schedule = self.request.event.wip_schedule
            qs = schedule.talks.filter(room__isnull=False).select_related('room')
        ctx['talk_slots'] = qs.filter(submission=self.submission).order_by('start').select_related('room')
        result = []
        other_submissions = schedule.slots.exclude(pk=self.submission.pk) if schedule else Submission.objects.none()
        for speaker in self.submission.speakers.all():
            speaker.talk_profile = speaker.event_profile(event=self.request.event)
            speaker.other_submissions = other_submissions.filter(speakers__in=[speaker]).select_related('event')
            result.append(speaker)
        ctx['speakers'] = result
        return ctx

    @context
    @cached_property
    def submission_description(self):
        return (
            self.submission.description
            or self.submission.abstract
            or _('The talk “{title}” at {event}').format(
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
        ).select_related('question')


class TalkReviewView(TalkView):
    model = Submission
    slug_field = 'review_code'
    template_name = 'agenda/talk.html'

    def has_permission(self):
        return True

    def get_object(self):
        obj = self.request.event.submissions.filter(
            review_code=self.kwargs['slug'],
            state__in=[
                SubmissionStates.SUBMITTED,
                SubmissionStates.ACCEPTED,
                SubmissionStates.CONFIRMED,
            ],
        ).first()
        if obj:
            return obj
        raise Http404()


class SingleICalView(EventPageMixin, DetailView):
    model = Submission
    slug_field = 'code'

    def get(self, request, event, **kwargs):
        talk = (
            self.get_object()
            .slots.filter(schedule=self.request.event.current_schedule, is_visible=True)
            .first()
        )
        if not talk:
            raise Http404()

        netloc = urlparse(settings.SITE_URL).netloc
        cal = vobject.iCalendar()
        cal.add('prodid').value = '-//pretalx//{}//{}'.format(
            netloc, talk.submission.code
        )
        talk.build_ical(cal)
        code = talk.submission.code
        resp = HttpResponse(cal.serialize(), content_type='text/calendar')
        resp[
            'Content-Disposition'
        ] = f'attachment; filename="{request.event.slug}-{code}.ics"'
        return resp


class FeedbackView(PermissionRequired, FormView):
    form_class = FeedbackForm
    template_name = 'agenda/feedback_form.html'
    permission_required = 'agenda.view_slot'

    def get_object(self):
        return self.request.event.talks.filter(
            code__iexact=self.kwargs['slug']
        ).first()

    @context
    @cached_property
    def talk(self):
        return self.get_object()

    @context
    @cached_property
    def can_give_feedback(self):
        return self.request.user.has_perm('agenda.give_feedback', self.talk)

    @context
    @cached_property
    def speakers(self):
        return self.talk.speakers.all()

    def get(self, *args, **kwargs):
        talk = self.talk
        if talk and self.request.user in self.speakers:
            return render(
                self.request,
                'agenda/feedback.html',
                context={
                    'talk': talk,
                    'feedback': talk.feedback.filter(
                        Q(speaker__isnull=True) | Q(speaker=self.request.user)
                    ).select_related('speaker'),
                },
            )
        return super().get(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['talk'] = self.talk
        return kwargs

    def form_valid(self, form):
        if not self.can_give_feedback:
            return super().form_invalid(form)
        result = super().form_valid(form)
        form.save()
        messages.success(self.request, phrases.agenda.feedback_success)
        return result

    def get_success_url(self):
        return self.get_object().urls.public
