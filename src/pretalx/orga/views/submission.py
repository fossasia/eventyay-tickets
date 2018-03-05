import random
from datetime import timedelta

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import override, ugettext as _
from django.views.generic import ListView, TemplateView, View

from pretalx.common.mixins.views import (
    ActionFromUrl, Filterable, PermissionRequired, Sortable,
)
from pretalx.common.urls import build_absolute_uri
from pretalx.common.views import CreateOrUpdateView
from pretalx.mail.models import QueuedMail
from pretalx.orga.forms import SubmissionForm
from pretalx.person.models import SpeakerProfile, User
from pretalx.submission.forms import SubmissionFilterForm
from pretalx.submission.models import (
    Question, Submission, SubmissionError, SubmissionStates,
)


def create_user_as_orga(email, submission=None):
    if not email:
        return

    nick = email.split('@')[0].lower()
    while User.objects.filter(nick__iexact=nick).exists():
        nick += random.choice([
            '_1', '_2', '_11', '_42', '_the_first', '_the_third',
            '_speaker', '_third_of_their_name', '_', '123', nick
        ])

    user = User.objects.create_user(
        nick=nick,
        password=get_random_string(32),
        email=email.lower(),
        pw_reset_token=get_random_string(32),
        pw_reset_time=now() + timedelta(days=7),
    )
    with override(submission.content_locale):
        invitation_link = build_absolute_uri('cfp:event.recover', kwargs={'event': submission.event.slug, 'token': user.pw_reset_token})
        invitation_text = _('''Hi!

You have been set as the speaker of a submission to the Call for Participation
of {event}, titled »{title}«. An account has been created for you – please follow
this link to set your account password.

{invitation_link}

Afterwards, you can edit your user profile and see the state of your submission.

The {event} orga crew''').format(event=submission.event.name, title=submission.title, invitation_link=invitation_link)
        QueuedMail.objects.create(
            event=submission.event,
            to=user.email,
            reply_to=submission.event.email,
            subject=str(_('You have been added to a submission for {event}').format(event=submission.event.name)),
            text=invitation_text,
        )
    return user


class SubmissionViewMixin(PermissionRequired):

    def get_object(self):
        return get_object_or_404(
            self.request.event.submissions,
            code__iexact=self.kwargs.get('code'),
        )

    @cached_property
    def object(self):
        return self.get_object()

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['submission'] = self.get_object()
        return ctx


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
        if self.is_allowed:
            self.do()
        else:
            self.do(force=True)
        return redirect(self.get_success_url())

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['target'] = self.target
        ctx['next'] = self.request.GET.get('next')
        return ctx


class SubmissionSpeakersAdd(SubmissionViewMixin, View):
    permission_required = 'submission.edit_speaker_list'

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.get_object()
        nick = request.POST.get('nick')
        try:
            if '@' in nick:
                speaker = User.objects.get(email__iexact=nick)
            else:
                speaker = User.objects.get(nick__iexact=nick)
        except User.DoesNotExist:
            speaker = create_user_as_orga(request.POST.get('nick'), submission=submission)
        if not speaker:
            messages.error(request, _('Please provide a valid nick or email address!'))
        else:
            if submission not in speaker.submissions.all():
                speaker.submissions.add(submission)
                speaker.save(update_fields=['submissions'])
                submission.log_action('pretalx.submission.speakers.add', person=request.user, orga=True)
                messages.success(request, _('The speaker has been added to the submission.'))
            else:
                messages.warning(request, _('The speaker was already part of the submission.'))
        if not speaker.profiles.filter(event=request.event).exists():
            SpeakerProfile.objects.create(user=speaker, event=request.event)
        return redirect(submission.orga_urls.speakers)


class SubmissionSpeakersDelete(SubmissionViewMixin, View):
    permission_required = 'submission.edit_speaker_list'

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.get_object()
        speaker = get_object_or_404(User, nick__iexact=request.GET.get('nick'))

        if submission in speaker.submissions.all():
            speaker.submissions.remove(submission)
            speaker.save(update_fields=['submissions'])
            submission.log_action('pretalx.submission.speakers.remove', person=request.user, orga=True)
            messages.success(request, _('The speaker has been removed from the submission.'))
        else:
            messages.warning(request, _('The speaker was not part of this submission.'))
        return redirect(submission.orga_urls.speakers)


class SubmissionSpeakers(SubmissionViewMixin, TemplateView):
    template_name = 'orga/submission/speakers.html'
    permission_required = 'submission.view_submission'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        submission = context['submission']
        context['speakers'] = [{
                'id': speaker.id,
                'name': speaker.get_display_name(),
                'nick': speaker.nick,
                'biography': speaker.profiles.get_or_create(event=submission.event)[0].biography,
                'other_submissions': speaker.submissions.filter(event=submission.event).exclude(code=submission.code),
            } for speaker in submission.speakers.all()
        ]
        context['users'] = User.objects.all()  # TODO: yeah, no
        return context


class SubmissionQuestions(SubmissionViewMixin, TemplateView):
    template_name = 'orga/submission/answer_list.html'
    permission_required = 'submission.view_submission'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        submission = context['submission']
        answers = [
            question.answers.filter(submission=submission).first()
            for question in Question.all_objects.filter(event=submission.event, target='submission')
        ]
        context.update({
            'answer_list': [a for a in answers if a],
            'submission': submission,
        })
        return context


class SubmissionContent(ActionFromUrl, SubmissionViewMixin, CreateOrUpdateView):
    model = Submission
    form_class = SubmissionForm
    template_name = 'orga/submission/content.html'
    permission_required = 'submission.view_submission'

    @property
    def write_permission_required(self):
        if 'code' in self.kwargs:
            return 'submission.edit_submission'
        return 'orga.create_submission'

    def get_permission_required(self):
        if 'code' in self.kwargs:
            return ['submission.view_submission']
        return ['orga.create_submission']

    def get_permission_object(self):
        return self.get_object() or self.request.event

    def get_object(self):
        return self.request.event.submissions.filter(code__iexact=self.kwargs.get('code')).first()

    def get_success_url(self) -> str:
        self.kwargs.update({'code': self.object.code})
        return self.object.orga_urls.base

    def form_valid(self, form):
        created = invited = not self.object
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        self.object = form.instance

        if created:
            email = form.cleaned_data['speaker']
            try:
                if '@' in email:
                    speaker = User.objects.get(email__iexact=email)
                else:
                    speaker = User.objects.get(nick__iexact=email)
                invited = False
            except User.DoesNotExist:
                speaker = create_user_as_orga(email=email, submission=form.instance)

            form.instance.speakers.add(speaker)

        if form.has_changed():
            action = 'pretalx.submission.' + ('create' if created else 'update')
            form.instance.log_action(action, person=self.request.user, orga=True)
        if created and invited:
            messages.success(self.request, _('The submission has been created and the speaker has been invited to add an account!'))
        elif created:  # TODO: send email!
            messages.success(self.request, _('The submission has been created; the speaker already had an account on this system.'))
        else:
            messages.success(self.request, _('The submission has been updated!'))
        return ret

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs


class SubmissionList(PermissionRequired, Sortable, Filterable, ListView):
    model = Submission
    context_object_name = 'submissions'
    template_name = 'orga/submission/list.html'
    default_filters = ('code__icontains', 'speakers__name__icontains', 'speakers__nick__icontains', 'title__icontains')
    filter_fields = ('submission_type', 'state')
    filter_form_class = SubmissionFilterForm
    sortable_fields = ('code', 'title', 'submission_type', 'state')
    permission_required = 'orga.view_submissions'
    paginate_by = 25

    def get_permission_object(self):
        return self.request.event

    def get_queryset(self):
        qs = self.request.event.submissions.select_related('submission_type').order_by('-id').all()
        qs = self.filter_queryset(qs)
        qs = self.sort_queryset(qs)
        return qs


class FeedbackList(SubmissionViewMixin, ListView):
    template_name = 'orga/submission/feedback_list.html'
    context_object_name = 'feedback'
    paginate_by = 25
    permission_required = 'submission.view_feedback'

    def get_queryset(self):
        return self.get_object().feedback.all().order_by('pk')
