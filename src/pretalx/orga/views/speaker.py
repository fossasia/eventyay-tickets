from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.views.generic import ListView, View

from pretalx.common.mixins.views import (
    ActionFromUrl, Filterable, PermissionRequired, Sortable,
)
from pretalx.common.views import CreateOrUpdateView
from pretalx.person.forms import (
    SpeakerFilterForm, SpeakerInformationForm, SpeakerProfileForm,
)
from pretalx.person.models import SpeakerInformation, SpeakerProfile, User
from pretalx.submission.models.submission import SubmissionStates


class SpeakerList(PermissionRequired, Sortable, Filterable, ListView):
    model = SpeakerProfile
    template_name = 'orga/speaker/list.html'
    context_object_name = 'speakers'
    default_filters = ('user__nick__icontains', 'user__email__icontains', 'user__name__icontains')
    sortable_fields = ('user__nick', 'user__email', 'user__name')
    default_sort_field = 'user__name'
    paginate_by = 25
    permission_required = 'orga.view_speakers'

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['filter_form'] = SpeakerFilterForm()
        return ctx

    def get_queryset(self):
        qs = SpeakerProfile.objects.filter(event=self.request.event)
        qs = self.filter_queryset(qs)
        if 'role' in self.request.GET:
            # TODO: this returns speakers accepted for *other* events. SubQuery time
            if self.request.GET['role'] == 'true':
                qs = qs.filter(user__submissions__state__in=[SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED])
            elif self.request.GET['role'] == 'false':
                qs = qs.exclude(user__submissions__state__in=[SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED])
        qs = self.sort_queryset(qs)
        return qs


class SpeakerDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    template_name = 'orga/speaker/form.html'
    form_class = SpeakerProfileForm
    model = User
    permission_required = 'orga.view_speaker'
    write_permission_required = 'orga.change_speaker'

    def get_object(self):
        return get_object_or_404(
            User.objects.filter(submissions__in=self.request.event.submissions.all()).order_by('id').distinct(),
            pk=self.kwargs['pk'],
        )

    @cached_property
    def object(self):
        return self.get_object()

    def get_permission_object(self):
        return self.get_object().profiles.filter(event=self.request.event).first()

    @cached_property
    def permission_object(self):
        return self.get_permission_object()

    def get_success_url(self) -> str:
        return reverse('orga:speakers.view', kwargs={'event': self.request.event.slug, 'pk': self.kwargs['pk']})

    def get_context_data(self, *args, **kwargs):
        from pretalx.submission.models import QuestionTarget
        ctx = super().get_context_data(*args, **kwargs)
        submissions = self.request.event.submissions.filter(speakers__in=[self.object])
        ctx['submission_count'] = submissions.count()
        ctx['submissions'] = submissions
        ctx['questions'] = [{
            'question': question,
            'answers': question.answers.filter(person=self.object)
        } for question in self.request.event.questions.filter(target__in=[QuestionTarget.SUBMISSION, QuestionTarget.SPEAKER])]
        ctx['questions'] = [q for q in ctx['questions'] if q['answers'].count() and any(a.answer is not None for a in q['answers'])]
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'The speaker profile has been updated.')
        if form.has_changed():
            profile = self.object.profiles.filter(event=self.request.event).first()
            if profile:
                profile.log_action('pretalx.user.profile.update', person=self.request.user, orga=True)
        return super().form_valid(form)

    def get_form_kwargs(self, *args, **kwargs):
        ret = super().get_form_kwargs(*args, **kwargs)
        ret.update({
            'event': self.request.event,
            'user': self.get_object(),
        })
        return ret


class SpeakerToggleArrived(PermissionRequired, View):
    permission_required = 'orga.change_speaker'

    def get_object(self):
        return get_object_or_404(SpeakerProfile, event=self.request.event, user_id=self.kwargs['pk'])

    def dispatch(self, request, event, pk):
        profile = self.get_object()
        profile.has_arrived = not profile.has_arrived
        profile.save()
        action = 'pretalx.speaker.arrived' if profile.has_arrived else 'pretalx.speaker.unarrived'
        profile.user.log_action(action, data={'event': self.request.event.slug}, person=self.request.user, orga=True)
        if request.GET.get('from') == 'list':
            return redirect(reverse('orga:speakers.list', kwargs={'event': self.kwargs['event']}))
        return redirect(reverse(
            'orga:speakers.view',
            kwargs=self.kwargs,
        ))


class InformationList(PermissionRequired, ListView):
    model = SpeakerInformation
    template_name = 'orga/speaker/information_list.html'
    context_object_name = 'information'
    paginate_by = 25
    permission_required = 'orga.view_information'

    def get_permission_object(self):
        return self.request.event


class InformationDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    template_name = 'orga/speaker/information_form.html'
    form_class = SpeakerInformationForm
    model = SpeakerInformation
    permission_required = 'orga.view_information'
    write_permission_required = 'orga.change_information'

    def get_permission_object(self):
        return self.request.event

    def get_object(self):
        if 'pk' in self.kwargs:
            return self.request.event.information.filter(pk=self.kwargs['pk']).first()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.pop('read_only', None)
        return kwargs

    def form_valid(self, form):
        if not hasattr(form.instance, 'event') or not form.instance.event:
            form.instance.event = self.request.event
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.event.orga_urls.information


class InformationDelete(PermissionRequired, View):
    write_permission_required = 'orga.change_information'
