import json
from collections import Counter
from datetime import timedelta

from dateutil import rrule
from django.contrib import messages
from django.db import transaction
from django.forms.models import BaseModelFormSet, inlineformset_factory
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.http import is_safe_url
from django.utils.timezone import now
from django.utils.translation import override, ugettext as _
from django.views.generic import ListView, TemplateView, View

from pretalx.common.mixins.views import (
    ActionFromUrl, Filterable, PermissionRequired, Sortable,
)
from pretalx.common.models import ActivityLog
from pretalx.common.urls import build_absolute_uri
from pretalx.common.views import CreateOrUpdateView
from pretalx.mail.models import QueuedMail
from pretalx.orga.forms import SubmissionForm
from pretalx.person.models import SpeakerProfile, User
from pretalx.submission.forms import QuestionsForm, ResourceForm, SubmissionFilterForm
from pretalx.submission.models import (
    Resource, Submission, SubmissionError, SubmissionStates,
)


def create_user_as_orga(email, submission=None, name=None):
    if not email:
        return

    user = User.objects.create_user(
        password=get_random_string(32),
        email=email.lower(),
        name=name,
        pw_reset_token=get_random_string(32),
        pw_reset_time=now() + timedelta(days=7),
    )
    SpeakerProfile.objects.get_or_create(user=user, event=submission.event)
    with override(submission.content_locale):
        invitation_link = build_absolute_uri(
            'cfp:event.recover',
            kwargs={'event': submission.event.slug, 'token': user.pw_reset_token},
        )
        invitation_text = _(
            '''Hi!

You have been set as the speaker of a submission to the Call for Participation
of {event}, titled »{title}«. An account has been created for you – please follow
this link to set your account password.

{invitation_link}

Afterwards, you can edit your user profile and see the state of your submission.

The {event} orga crew'''
        ).format(
            event=submission.event.name,
            title=submission.title,
            invitation_link=invitation_link,
        )
        QueuedMail.objects.create(
            event=submission.event,
            to=user.email,
            reply_to=submission.event.email,
            subject=str(
                _('You have been added to a submission for {event}').format(
                    event=submission.event.name
                )
            ),
            text=invitation_text,
        )
    return user


class SubmissionViewMixin(PermissionRequired):
    def get_object(self):
        return get_object_or_404(
            self.request.event.submissions(manager='all_objects'),
            code__iexact=self.kwargs.get('code'),
        )

    @cached_property
    def object(self):
        return self.get_object()

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['submission'] = self.object
        return context


class SubmissionStateChange(SubmissionViewMixin, TemplateView):
    permission_required = 'orga.change_submission_state'
    template_name = 'orga/submission/state_change.html'
    TARGETS = {
        'submit': SubmissionStates.SUBMITTED,
        'accept': SubmissionStates.ACCEPTED,
        'reject': SubmissionStates.REJECTED,
        'confirm': SubmissionStates.CONFIRMED,
        'delete': SubmissionStates.DELETED,
        'withdraw': SubmissionStates.WITHDRAWN,
        'cancel': SubmissionStates.CANCELED,
    }

    @cached_property
    def target(self) -> str:
        """ Returns one of submit|accept|reject|confirm|delete|withdraw|cancel """
        return self.TARGETS[self.request.resolver_match.url_name.split('.')[-1]]

    @cached_property
    def is_allowed(self):
        return self.target in SubmissionStates.valid_next_states[self.object.state]

    def do(self, force=False):
        method = getattr(self.object, SubmissionStates.method_names[self.target])
        try:
            method(person=self.request.user, force=force, orga=True)
        except SubmissionError as e:
            messages.error(self.request, e.message)

    def get_success_url(self):
        next_url = self.request.POST.get('next', '')

        if next_url == self.object.event.orga_urls.reviews:
            return next_url

        return self.object.orga_urls.base

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        if self.target == self.object.state:
            messages.info(
                request,
                _(
                    'Somebody else was faster than you: this submission was already in the state you wanted to change it to.'
                ),
            )
        elif self.is_allowed:
            self.do()
        else:
            self.do(force=True)
        url = self.request.GET.get('next')
        if url and is_safe_url(url, self.request.get_host()):
            return redirect(url)
        return redirect(self.object.orga_urls.base)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['target'] = self.target
        context['next'] = self.request.GET.get('next')
        return context


class SubmissionSpeakersAdd(SubmissionViewMixin, View):
    permission_required = 'submission.edit_speaker_list'

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.object
        email = request.POST.get('speaker')
        name = request.POST.get('name')
        try:
            speaker = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            speaker = create_user_as_orga(email, submission=submission, name=name)
        if not speaker:
            messages.error(request, _('Please provide a valid email address!'))
        else:
            if submission not in speaker.submissions.all():
                speaker.submissions.add(submission)
                speaker.save(update_fields=['submissions'])
                submission.log_action(
                    'pretalx.submission.speakers.add', person=request.user, orga=True
                )
                messages.success(
                    request, _('The speaker has been added to the submission.')
                )
            else:
                messages.warning(
                    request, _('The speaker was already part of the submission.')
                )
            if not speaker.profiles.filter(event=request.event).exists():
                SpeakerProfile.objects.create(user=speaker, event=request.event)
        return redirect(submission.orga_urls.speakers)


class SubmissionSpeakersDelete(SubmissionViewMixin, View):
    permission_required = 'submission.edit_speaker_list'

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.object
        speaker = get_object_or_404(User, pk=request.GET.get('id'))

        if submission in speaker.submissions.all():
            speaker.submissions.remove(submission)
            speaker.save(update_fields=['submissions'])
            submission.log_action(
                'pretalx.submission.speakers.remove', person=request.user, orga=True
            )
            messages.success(
                request, _('The speaker has been removed from the submission.')
            )
        else:
            messages.warning(request, _('The speaker was not part of this submission.'))
        return redirect(submission.orga_urls.speakers)


class SubmissionSpeakers(SubmissionViewMixin, TemplateView):
    template_name = 'orga/submission/speakers.html'
    permission_required = 'orga.view_submissions'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        submission = context['submission']
        context['speakers'] = [
            {
                'id': speaker.id,
                'name': speaker.get_display_name(),
                'biography': speaker.profiles.get_or_create(event=submission.event)[
                    0
                ].biography,
                'other_submissions': speaker.submissions.filter(
                    event=submission.event
                ).exclude(code=submission.code),
            }
            for speaker in submission.speakers.all()
        ]
        context['users'] = User.objects.all()  # TODO: yeah, no
        return context


class SubmissionContent(ActionFromUrl, SubmissionViewMixin, CreateOrUpdateView):
    model = Submission
    form_class = SubmissionForm
    template_name = 'orga/submission/content.html'
    permission_required = 'orga.view_submissions'

    def get_object(self):
        try:
            return super().get_object()
        except Http404 as not_found:
            if self.request.path.rstrip('/').endswith('/new'):
                return None
            return not_found

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = self.formset
        context['questions_form'] = self.questions_form
        return context

    @cached_property
    def write_permission_required(self):
        if 'code' in self.kwargs:
            return 'submission.edit_submission'
        return 'orga.create_submission'

    @cached_property
    def formset(self):
        formset_class = inlineformset_factory(
            Submission,
            Resource,
            form=ResourceForm,
            formset=BaseModelFormSet,
            can_delete=True,
            extra=0,
        )
        submission = self.get_object()
        return formset_class(
            self.request.POST if self.request.method == 'POST' else None,
            files=self.request.FILES if self.request.method == 'POST' else None,
            queryset=submission.resources.all()
            if submission
            else Resource.objects.none(),
            prefix='resource',
        )

    @cached_property
    def questions_form(self):
        submission = self.get_object()
        return QuestionsForm(
            self.request.POST if self.request.method == 'POST' else None,
            files=self.request.FILES if self.request.method == 'POST' else None,
            target='submission',
            submission=submission,
            event=self.request.event,
        )

    def save_formset(self, obj):
        if self.formset.is_valid():
            for form in self.formset.initial_forms:
                if form in self.formset.deleted_forms:
                    if not form.instance.pk:
                        continue
                    obj.log_action(
                        'pretalx.submission.resource.delete',
                        person=self.request.user,
                        data={'id': form.instance.pk},
                    )
                    form.instance.delete()
                    form.instance.pk = None
                elif form.has_changed():
                    form.instance.submission = obj
                    form.save()
                    change_data = {
                        k: form.cleaned_data.get(k) for k in form.changed_data
                    }
                    change_data['id'] = form.instance.pk
                    obj.log_action(
                        'pretalx.submission.resource.update', person=self.request.user
                    )

            for form in self.formset.extra_forms:
                if not form.has_changed():
                    continue
                if self.formset._should_delete_form(form):
                    continue
                form.instance.submission = obj
                form.save()
                obj.log_action(
                    'pretalx.submission.resource.create',
                    person=self.request.user,
                    orga=True,
                    data={'id': form.instance.pk},
                )

            return True
        return False

    def get_permission_required(self):
        if 'code' in self.kwargs:
            return ['orga.view_submissions']
        return ['orga.create_submission']

    def get_permission_object(self):
        return self.object or self.request.event

    def get_success_url(self) -> str:
        self.kwargs.update({'code': self.object.code})
        return self.object.orga_urls.base

    @transaction.atomic()
    def form_valid(self, form):
        created = invited = not self.object
        form.instance.event = self.request.event
        form.save()
        self.object = form.instance
        self.questions_form.submission = self.object
        if not self.questions_form.is_valid():
            return self.get(self.request, *self.args, **self.kwargs)
        self.questions_form.save()

        if created:
            email = form.cleaned_data['speaker']
            try:
                speaker = User.objects.get(email__iexact=email)
                invited = False
            except User.DoesNotExist:
                speaker = create_user_as_orga(
                    email=email,
                    name=form.cleaned_data['speaker_name'],
                    submission=form.instance,
                )

            form.instance.speakers.add(speaker)
        else:
            formset_result = self.save_formset(form.instance)
            if not formset_result:
                return self.get(self.request, *self.args, **self.kwargs)

        if form.has_changed():
            action = 'pretalx.submission.' + ('create' if created else 'update')
            form.instance.log_action(action, person=self.request.user, orga=True)
        if created and invited:
            messages.success(
                self.request,
                _(
                    'The submission has been created and the speaker has been invited to add an account!'
                ),
            )
        elif created:  # TODO: send email!
            messages.success(
                self.request,
                _(
                    'The submission has been created; the speaker already had an account on this system.'
                ),
            )
        else:
            messages.success(self.request, _('The submission has been updated!'))
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs


class SubmissionList(PermissionRequired, Sortable, Filterable, ListView):
    model = Submission
    context_object_name = 'submissions'
    template_name = 'orga/submission/list.html'
    default_filters = (
        'code__icontains',
        'speakers__name__icontains',
        'title__icontains',
    )
    filter_fields = ('submission_type', 'state')
    filter_form_class = SubmissionFilterForm
    sortable_fields = ('code', 'title', 'state', 'is_featured')
    permission_required = 'orga.view_submissions'
    paginate_by = 25

    def get_permission_object(self):
        return self.request.event

    def get_queryset(self):
        qs = (
            self.request.event.submissions(manager='all_objects')
            .select_related('submission_type')
            .order_by('-id')
            .all()
        )
        qs = self.filter_queryset(qs)
        if 'state' not in self.request.GET:
            qs = qs.exclude(state='deleted')
        qs = self.sort_queryset(qs)
        return qs.distinct()

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        data = Counter(
            timestamp.date()
            for timestamp in ActivityLog.objects.filter(
                event=self.request.event, action_type='pretalx.submission.create'
            ).values_list('timestamp', flat=True)
        )
        dates = data.keys()
        if len(dates) > 1:
            date_range = rrule.rrule(
                rrule.DAILY,
                count=(max(dates) - min(dates)).days + 1,
                dtstart=min(dates),
            )
            if len(data) > 1:
                context['timeline_data'] = json.dumps(
                    [
                        {"x": date.isoformat(), "y": data.get(date.date(), 0)}
                        for date in date_range
                    ]
                )
        return context


class FeedbackList(SubmissionViewMixin, ListView):
    template_name = 'orga/submission/feedback_list.html'
    context_object_name = 'feedback'
    paginate_by = 25
    permission_required = 'submission.view_feedback'

    def get_queryset(self):
        return self.object.feedback.all().order_by('pk')


class ToggleFeatured(SubmissionViewMixin, View):
    permission_required = 'orga.change_submissions'

    def get_permission_object(self):
        return self.object or self.request.event

    def post(self, *args, **kwargs):
        self.object.is_featured = not self.object.is_featured
        self.object.save(update_fields=['is_featured'])
        return HttpResponse()
