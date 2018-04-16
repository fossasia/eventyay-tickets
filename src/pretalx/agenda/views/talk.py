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
from django.views.generic import DetailView, FormView

from pretalx.cfp.views.event import EventPageMixin
from pretalx.common.mixins.views import PermissionRequired
from pretalx.common.phrases import phrases
from pretalx.schedule.models import TalkSlot
from pretalx.submission.forms import FeedbackForm
from pretalx.submission.models import Feedback, Submission


class TalkView(PermissionRequired, DetailView):
    context_object_name = 'talk'
    model = Submission
    slug_field = 'code'
    template_name = 'agenda/talk.html'
    permission_required = 'agenda.view_slot'

    def get_object(self):
        with suppress(AttributeError, TalkSlot.DoesNotExist):
            return self.request.event.current_schedule.talks.get(submission__code__iexact=self.kwargs['slug'], is_visible=True)
        if self.request.is_orga:
            with suppress(AttributeError, TalkSlot.DoesNotExist):
                return self.request.event.wip_schedule.talks.get(submission__code__iexact=self.kwargs['slug'], is_visible=True)
        raise Http404()

    @csp_update(CHILD_SRC="https://media.ccc.de")  # TODO: only do this if obj.recording_url and obj.recording_source are set
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        if self.request.event.current_schedule:
            qs = self.request.event.current_schedule.talks
        elif self.request.is_orga:
            qs = self.request.event.wip_schedule.talks
        else:
            qs = TalkSlot.objects.none()
        event_talks = qs.exclude(submission=self.object.submission)
        slot = self.get_object()
        context['submission_description'] = slot.submission.description or slot.submission.abstract or _('The talk »{title}« at {event}').format(title=slot.submission.title, event=slot.submission.event.name)
        context['speakers'] = []
        for speaker in slot.submission.speakers.all():  # TODO: there's bound to be an elegant annotation for this
            speaker.talk_profile = speaker.profiles.filter(event=self.request.event).first()
            speaker.other_talks = event_talks.filter(submission__speakers__in=[speaker])
            context['speakers'].append(speaker)
        return context


class SingleICalView(EventPageMixin, DetailView):
    model = Submission
    slug_field = 'code'

    def get(self, request, event, **kwargs):
        talk = self.get_object().slots.filter(schedule=self.request.event.current_schedule).first()
        netloc = urlparse(settings.SITE_URL).netloc

        cal = vobject.iCalendar()
        if talk:
            cal.add('prodid').value = '-//pretalx//{}//{}'.format(netloc, talk.submission.code)
            talk.build_ical(cal)
            code = talk.submission.code
        else:
            code = 'NONE'

        resp = HttpResponse(cal.serialize(), content_type='text/calendar')
        resp['Content-Disposition'] = f'attachment; filename="{request.event.slug}-{code}.ics"'
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
                    'feedback': talk.feedback.filter(Q(speaker__isnull=True) | Q(speaker=self.request.user)),
                }
            )
        return super().get(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['talk'] = self.get_object()
        return kwargs

    def get_context_data(self):
        context = super().get_context_data()
        context['talk'] = self.get_object()
        return context

    def form_valid(self, form):
        if not form.instance.talk.does_accept_feedback:
            return super().form_invalid(form)
        result = super().form_valid(form)
        form.save()
        messages.success(self.request, phrases.agenda.feedback_success)
        return result

    def get_success_url(self):
        return self.get_object().urls.public
