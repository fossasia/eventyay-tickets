from contextlib import suppress
from urllib.parse import urlparse

import vobject
from csp.decorators import csp_update
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView, FormView, ListView

from pretalx.cfp.views.event import EventPageMixin
from pretalx.common.mixins.views import Filterable, PermissionRequired
from pretalx.common.phrases import phrases
from pretalx.person.models.profile import SpeakerProfile
from pretalx.schedule.models import TalkSlot
from pretalx.submission.forms import FeedbackForm
from pretalx.submission.models import Feedback, Submission


class TalkList(PermissionRequired, Filterable, ListView):
    context_object_name = 'talks'
    model = Submission
    template_name = 'agenda/talks.html'
    permission_required = 'agenda.view_schedule'
    default_filters = (
        'submission__speakers__name__icontains',
        'submission__title__icontains',
    )

    def get_queryset(self):
        return self.filter_queryset(self.request.event.talks)

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['search'] = self.request.GET.get('q')
        return context


class SpeakerList(PermissionRequired, Filterable, ListView):
    context_object_name = 'speakers'
    template_name = 'agenda/speakers.html'
    permission_required = 'agenda.view_schedule'
    default_filters = ('user__name__icontains',)

    def get_queryset(self):
        qs = SpeakerProfile.objects.filter(
            user__in=self.request.event.speakers, event=self.request.event
        )
        return self.filter_queryset(qs)

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['search'] = self.request.GET.get('q')
        return context


class TalkView(PermissionRequired, DetailView):
    context_object_name = 'talk'
    model = Submission
    slug_field = 'code'
    template_name = 'agenda/talk.html'
    permission_required = 'agenda.view_slot'

    def get_object(self, queryset=None):
        with suppress(AttributeError, TalkSlot.DoesNotExist):
            return self.request.event.current_schedule.talks.get(
                submission__code__iexact=self.kwargs['slug'], is_visible=True
            )
        if getattr(self.request, 'is_orga', False):
            with suppress(AttributeError, TalkSlot.DoesNotExist):
                return self.request.event.wip_schedule.talks.get(
                    submission__code__iexact=self.kwargs['slug'], is_visible=True
                )
        raise Http404()

    @csp_update(CHILD_SRC="https://media.ccc.de")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        slot = self.object
        qs = TalkSlot.objects.none()
        if self.request.event.current_schedule:
            qs = self.request.event.current_schedule.talks.filter(is_visible=True)
        elif self.request.is_orga:
            qs = self.request.event.wip_schedule.talks
        event_talks = qs.exclude(submission=slot.submission)
        context['submission'] = slot.submission
        context['submission_description'] = (
            slot.submission.description
            or slot.submission.abstract
            or _('The talk »{title}« at {event}').format(
                title=slot.submission.title, event=slot.submission.event.name
            )
        )
        context['speakers'] = []
        for speaker in slot.submission.speakers.all():
            speaker.talk_profile = speaker.event_profile(event=self.request.event)
            speaker.other_talks = event_talks.filter(submission__speakers__in=[speaker])
            context['speakers'].append(speaker)
        return context


class TalkReviewView(DetailView):
    model = Submission
    slug_field = 'review_code'
    template_name = 'agenda/talk.html'


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
    model = Feedback
    form_class = FeedbackForm
    template_name = 'agenda/feedback_form.html'
    permission_required = 'agenda.give_feedback'

    def get_object(self):
        return Submission.objects.filter(
            event=self.request.event,
            code__iexact=self.kwargs['slug'],
            slots__in=self.request.event.current_schedule.talks.filter(is_visible=True),
        ).first()

    def get(self, *args, **kwargs):
        talk = self.get_object()
        if talk and self.request.user in talk.speakers.all():
            return render(
                self.request,
                'agenda/feedback.html',
                context={
                    'talk': talk,
                    'feedback': talk.feedback.filter(
                        Q(speaker__isnull=True) | Q(speaker=self.request.user)
                    ),
                },
            )
        return super().get(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['talk'] = self.get_object()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['talk'] = self.get_object()
        return context

    def form_valid(self, form):
        result = super().form_valid(form)
        form.save()
        messages.success(self.request, phrases.agenda.feedback_success)
        return result

    def get_success_url(self):
        return self.get_object().urls.public
