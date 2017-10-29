import urllib

from csp.decorators import csp_update
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import (
    DetailView, FormView, ListView, TemplateView, UpdateView, View,
)

from pretalx.cfp.forms.submissions import (
    InfoForm, QuestionsForm, SubmissionInvitationForm,
)
from pretalx.cfp.views.event import LoggedInEventPageMixin
from pretalx.person.forms import LoginInfoForm, SpeakerProfileForm
from pretalx.submission.models import Submission, SubmissionStates


@method_decorator(csp_update(STYLE_SRC="'self' 'unsafe-inline'", IMG_SRC="https://www.gravatar.com"), name='dispatch')
class ProfileView(LoggedInEventPageMixin, TemplateView):
    template_name = 'cfp/event/user_profile.html'

    @cached_property
    def login_form(self):
        return LoginInfoForm(user=self.request.user,
                             data=(self.request.POST
                                   if self.request.method == 'POST'
                                   and self.request.POST.get('form') == 'login'
                                   else None))

    @cached_property
    def profile_form(self):
        if self.request.method == 'POST' and self.request.POST.get('form') == 'profile':
            return SpeakerProfileForm(
                user=self.request.user,
                event=self.request.event,
                read_only=False,
                data=self.request.POST,
                files=self.request.FILES,
            )
        return SpeakerProfileForm(
            user=self.request.user,
            event=self.request.event,
            read_only=False,
            data=None,
        )

    @cached_property
    def questions_form(self):
        return QuestionsForm(
            data=self.request.POST if self.request.method == 'POST' else None,
            speaker=self.request.user,
            event=self.request.event,
            target='speaker',
            request_user=self.request.user,
        )

    def get_context_data(self, event):
        ctx = super().get_context_data()
        ctx['login_form'] = self.login_form
        ctx['profile_form'] = self.profile_form
        ctx['questions_form'] = self.questions_form
        ctx['questions_exist'] = self.request.event.questions.filter(active=True, target='speaker').exists()
        return ctx

    def post(self, request, *args, **kwargs):
        if self.login_form.is_bound:
            if self.login_form.is_valid():
                self.login_form.save()
                messages.success(self.request, _('Your changes have been saved.'))
                request.user.log_action('pretalx.user.password.update', person=request.user)
                return redirect('cfp:event.user.view', event=self.request.event.slug)
        elif self.profile_form.is_bound:
            if self.profile_form.is_valid():
                self.profile_form.save()
                messages.success(self.request, _('Your changes have been saved.'))
                profile = self.request.user.profiles.get_or_create(event=self.request.event)[0]
                profile.log_action('pretalx.user.profile.update', person=request.user)
                return redirect('cfp:event.user.view', event=self.request.event.slug)
        elif self.questions_form.is_bound:
            if self.questions_form.is_valid():
                self.questions_form.save()
                messages.success(self.request, _('Your changes have been saved.'))
                return redirect('cfp:event.user.view', event=self.request.event.slug)

        messages.error(self.request, _('Oh :( We had trouble saving your input. See below for details.'))
        return super().get(request, *args, **kwargs)


class SubmissionViewMixin:
    def get_object(self):
        try:
            return self.request.event.submissions.prefetch_related('answers', 'answers__options').get(
                speakers__in=[self.request.user],
                code__iexact=self.kwargs.get('code')
            )
        except Submission.DoesNotExist:
            try:
                # Backwards compatibility
                return self.request.event.submissions.prefetch_related('answers', 'answers__options').get(
                    speakers__in=[self.request.user],
                    id=self.kwargs.get('code')
                )
            except (Submission.DoesNotExist, ValueError):
                raise Http404()


class SubmissionsListView(LoggedInEventPageMixin, ListView):
    template_name = 'cfp/event/user_submissions.html'
    context_object_name = 'submissions'

    def get_queryset(self):
        return self.request.event.submissions.filter(speakers__in=[self.request.user])


class SubmissionsWithdrawView(LoggedInEventPageMixin, SubmissionViewMixin, DetailView):
    template_name = 'cfp/event/user_submission_withdraw.html'
    model = Submission
    context_object_name = 'submission'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.state == SubmissionStates.SUBMITTED:
            self.object.state = SubmissionStates.WITHDRAWN
            self.object.save(update_fields=['state'])
            self.object.log_action('pretalx.submission.withdrawal', person=request.user)
            messages.success(self.request, _('Your submission has been withdrawn.'))
        else:
            messages.error(self.request, _('Your submission can\'t be withdrawn at this time – please contact us if you need to withdraw your submission!'))
        return redirect('cfp:event.user.submissions', event=self.request.event.slug)


class SubmissionConfirmView(LoggedInEventPageMixin, SubmissionViewMixin, View):

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_anonymous:
            return redirect(request.event.urls.login)
        submission = self.get_object()
        if submission.state == SubmissionStates.ACCEPTED:
            submission.confirm(person=request.user)
            submission.log_action('pretalx.submission.confirm', person=request.user)
            messages.success(self.request, _('Your submission has been confirmed – we\'re looking forward to seeing you!'))
        elif submission.state == SubmissionStates.CONFIRMED:
            messages.success(self.request, _('This submission has already been confirmed – we\'re looking forward to seeing you!'))
        else:
            messages.error(self.request, _('This submission cannot be confirmed at this time – please contact us if you think this is an error.'))
        return redirect('cfp:event.user.submissions', event=self.request.event.slug)


class SubmissionsEditView(LoggedInEventPageMixin, SubmissionViewMixin, UpdateView):
    template_name = 'cfp/event/user_submission_edit.html'
    model = Submission
    form_class = InfoForm
    context_object_name = 'submission'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['qform'] = self.qform
        ctx['can_edit'] = self.can_edit
        return ctx

    @cached_property
    def qform(self):
        return QuestionsForm(
            data=self.request.POST if self.request.method == 'POST' else None,
            submission=self.object,
            event=self.request.event,
            readonly=not self.can_edit,
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid() and self.qform.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    @property
    def can_edit(self):
        return self.object.editable

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['readonly'] = not self.can_edit
        return kwargs

    def form_valid(self, form):
        if self.can_edit:
            form.save()
            self.qform.save()
            if form.has_changed():
                form.instance.log_action('pretalx.submission.update', person=self.request.user)
            messages.success(self.request, _('Your changes have been saved.'))
        else:
            messages.error(self.request, _('This submission cannot be edited anymore.'))
        return redirect('cfp:event.user.submissions', event=self.request.event.slug)


class DeleteAccountView(LoggedInEventPageMixin, View):

    def post(self, request, event):

        if request.POST.get('really'):
            from django.contrib.auth import logout
            request.user.deactivate()
            logout(request)
            messages.success(request, _('Your account has now been deleted.'))
            return redirect(request.event.urls.base)
        else:
            messages.error(request, _('Are you really sure? Please tick the box'))
            return redirect(request.event.urls.user + '?really')


class SubmissionInviteView(LoggedInEventPageMixin, SubmissionViewMixin, FormView):
    form_class = SubmissionInvitationForm
    template_name = 'cfp/event/user_submission_invitation.html'

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super().get_form_kwargs(*args, **kwargs)
        kwargs['submission'] = self.get_object()
        kwargs['speaker'] = self.request.user
        if 'email' in self.request.GET and not self.request.method == 'POST':
            initial = kwargs.get('initial', {})
            initial['speaker'] = urllib.parse.unquote(self.request.GET['email'])
            kwargs['initial'] = initial

            try:
                validate_email(initial['speaker'])
            except ValidationError:
                messages.warning(self.request, _('Please provide a valid email address.'))
        return kwargs

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['submission'] = self.get_object()
        ctx['invite_url'] = ctx['submission'].urls.accept_invitation.full(scheme='https')
        return ctx

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('The invitation was sent!'))
        submission.log_action('pretalx.submission.speakers.invite', person=self.request.user)
        return super().form_valid(form)

    def get_success_url(self):
        return self.get_object().urls.user_base


class SubmissionInviteAcceptView(LoggedInEventPageMixin, DetailView):
    template_name = 'cfp/event/invitation.html'
    context_object_name = 'submission'

    def get_object(self, *args, **kwargs):
        return Submission.objects.get(
            code__iexact=self.kwargs['code'],
            invitation_token__iexact=self.kwargs['invitation'],
        )

    def post(self, *args, **kwargs):
        submission = self.get_object()
        submission.speakers.add(self.request.user)  # TODO logging
        submission.save()
        messages.success(self.request, _('You are now part of this submission! Please fill in your profile below.'))
        return redirect('cfp:event.user.view', event=self.request.event.slug)
