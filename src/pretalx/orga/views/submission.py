import random
from datetime import timedelta

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django.utils.translation import override, ugettext as _
from django.views.generic import ListView, TemplateView, View

from pretalx.common.urls import build_absolute_uri
from pretalx.common.views import (
    ActionFromUrl, CreateOrUpdateView, Filterable, Sortable,
)
from pretalx.mail.models import QueuedMail
from pretalx.orga.forms import SubmissionForm
from pretalx.person.models import User
from pretalx.submission.models import Submission, SubmissionError


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


class SubmissionViewMixin:

    def get_object(self):
        return self.request.event.submissions.filter(code__iexact=self.kwargs.get('code')).first()


class SubmissionAccept(SubmissionViewMixin, View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.get_object()

        try:
            submission.accept(person=request.user)
            messages.success(request, _('The submission has been accepted.'))
        except SubmissionError:
            messages.error(request, _('A submission must be submitted or rejected to become accepted.'))
        return redirect(submission.orga_urls.base)


class SubmissionConfirm(SubmissionViewMixin, View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.get_object()

        try:
            submission.confirm(person=request.user, orga=True)
            messages.success(request, _('The submission has been confirmed.'))
        except SubmissionError:
            messages.error(request, _('A submission must be accepted to become confirmed.'))
        return redirect(submission.orga_urls.base)


class SubmissionReject(SubmissionViewMixin, View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.get_object()
        submission.reject(person=request.user)
        messages.success(request, _('The submission has been rejected.'))
        return redirect(submission.orga_urls.base)


class SubmissionSpeakersAdd(SubmissionViewMixin, View):
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
        return redirect(submission.orga_urls.speakers)


class SubmissionSpeakersDelete(SubmissionViewMixin, View):
    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.get_object()
        speaker = User.objects.get(nick__iexact=request.GET.get('nick'))

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

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['submission'] = self.get_object()
        context['speakers'] = context['submission'].speakers.all()
        context['users'] = User.objects.all()  # TODO: yeah, no
        return context


class SubmissionQuestions(SubmissionViewMixin, TemplateView):
    template_name = 'orga/submission/answer_list.html'

    def get_queryset(self):
        submission = self.get_object()
        return submission.answers.all()

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        submission = self.get_object()
        user_list = [{
            'speaker': user,
            'answers': submission.answers.all()  # TODO: filter
        } for user in submission.speakers.all()]
        context.update({
            'user_list': user_list,
            'submission': submission,
        })
        return context


class SubmissionContent(ActionFromUrl, SubmissionViewMixin, CreateOrUpdateView):
    model = Submission
    form_class = SubmissionForm
    template_name = 'orga/submission/content.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['submission'] = self.get_object()
        return context

    def get_success_url(self) -> str:
        self.kwargs.update({'pk': self.object.pk})
        return self.object.orga_urls.base

    def form_valid(self, form):
        created = invited = not self.object

        form.instance.event = self.request.event
        ret = super().form_valid(form)
        self.object = form.instance

        if created:
            # TODO: activate language by submission language
            email = form.cleaned_data['speaker']
            try:
                user = User.objects.get(email__iexact=email)
                invited = False
            except User.DoesNotExist:
                user = create_user_as_orga(email=email, submission=form.instance)

            form.instance.speakers.add(user)

        if form.has_changed():
            action = 'pretalx.submission.' + 'create' if created else 'update'
            form.instance.log_action(action, person=self.request.user, orga=True)
        if created and invited:
            messages.success(self.request, _('The submission has been created and the speaker has been invited to add an account!'))
        elif created:
            messages.success(self.request, _('The submission has been created; the speaker already had an account on this system.'))
        else:
            messages.success(self.request, _('The submission has been updated!'))
        return ret

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs


class SubmissionList(Sortable, Filterable, ListView):
    template_name = 'orga/submission/list.html'
    context_object_name = 'submissions'
    default_filters = ('code__icontains', 'speakers__name__icontains', 'speakers__nick__icontains', 'title__icontains')
    filter_fields = ('code', 'speakers', 'title', 'state')
    sortable_fields = ('code', 'title', 'submission_type', 'state')
    paginate_by = 25

    def get_queryset(self):
        qs = self.request.event.submissions.select_related('submission_type').order_by('title').all()
        qs = self.filter_queryset(qs)
        qs = self.sort_queryset(qs)
        return qs


class SubmissionDelete(SubmissionViewMixin, TemplateView):
    template_name = 'orga/submission/delete.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['submission'] = self.get_object()
        return ctx

    def post(self, request, *args, **kwargs):
        self.get_object().remove(person=request.user)
        messages.success(request, _('The submission has been deleted.'))
        return redirect(request.event.orga_urls.submissions)
