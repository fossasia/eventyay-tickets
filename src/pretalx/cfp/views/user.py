from django import forms
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import (
    DetailView, ListView, TemplateView, UpdateView, View,
)

from pretalx.cfp.forms.submissions import InfoForm, QuestionsForm
from pretalx.cfp.views.event import LoggedInEventPageMixin
from pretalx.person.forms import LoginInfoForm, SpeakerProfileForm
from pretalx.submission.models import Answer, Submission, SubmissionStates


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
        return SpeakerProfileForm(user=self.request.user,
                                  event=self.request.event,
                                  read_only=False,
                                  data=(self.request.POST
                                        if self.request.method == 'POST'
                                        and self.request.POST.get('form') == 'profile'
                                        else None))

    def get_context_data(self, event):
        ctx = super().get_context_data()
        ctx['login_form'] = self.login_form
        ctx['profile_form'] = self.profile_form
        return ctx

    def post(self, request, *args, **kwargs):
        if self.login_form.is_bound:
            if self.login_form.is_valid():
                self.login_form.save()
                messages.success(self.request, _('Your changes have been saved.'))
                profile = self.request.user.profiles.get(event=self.request.event)
                profile.log_action('pretalx.user.password.update', person=request.user)
                return redirect('cfp:event.user.view', event=self.request.event.slug)
        elif self.profile_form.is_bound:
            if self.profile_form.is_valid():
                self.profile_form.save()
                messages.success(self.request, _('Your changes have been saved.'))
                profile = self.request.user.profiles.get(event=self.request.event)
                profile.log_action('pretalx.user.profile.update', person=request.user)
                return redirect('cfp:event.user.view', event=self.request.event.slug)

        messages.error(self.request, _('Oh :( We had trouble saving your input. See below for details.'))
        return super().get(request, *args, **kwargs)


class SubmissionsListView(LoggedInEventPageMixin, ListView):
    template_name = 'cfp/event/user_submissions.html'
    context_object_name = 'submissions'

    def get_queryset(self):
        return self.request.event.submissions.filter(speakers__in=[self.request.user])


class SubmissionsWithdrawView(LoggedInEventPageMixin, DetailView):
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

    def get_object(self, queryset=None):
        try:
            return self.request.event.submissions.prefetch_related('answers', 'answers__options').get(
                speakers__in=[self.request.user],
                pk=self.kwargs.get('id')
            )
        except Submission.DoesNotExist:
            raise Http404()


class SubmissionConfirmView(LoggedInEventPageMixin, View):

    def dispatch(self, request, *args, **kwargs):
        submission = self.get_object()
        if submission.state == SubmissionStates.ACCEPTED:
            submission.state = SubmissionStates.CONFIRMED
            submission.save(update_fields=['state'])
            submission.log_action('pretalx.submission.confirmation', person=request.user)
            messages.success(self.request, _('Your submission has been confirmed – we\'re looking forward to seeing you!'))
        elif submission.state == SubmissionStates.CONFIRMED:
            messages.success(self.request, _('This submission has already been confirmed – we\'re looking forward to seeing you!'))
        else:
            messages.error(self.request, _('This submission cannot be confirmed at this time – please contact us if you think this is an error.'))
        return redirect('cfp:event.user.submissions', event=self.request.event.slug)

    def get_object(self):
        try:
            return self.request.event.submissions.get(
                speakers__in=[self.request.user],
                pk=self.kwargs.get('id')
            )
        except Submission.DoesNotExist:
            raise Http404()


class SubmissionsEditView(LoggedInEventPageMixin, UpdateView):
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
            readonly=not self.can_edit
        )

    def get_object(self, queryset=None):
        try:
            return self.request.event.submissions.prefetch_related('answers', 'answers__options').get(
                speakers__in=[self.request.user],
                pk=self.kwargs.get('id')
            )
        except Submission.DoesNotExist:
            raise Http404()

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
            self.questions_save()
            if form.has_changed():
                form.instance.log_action('pretalx.submission.update', person=self.request.user)
            messages.success(self.request, _('Your changes have been saved.'))
        else:
            messages.error(self.request, _('This submission cannot be edited anymore.'))
        return redirect('cfp:event.user.submissions', event=self.request.event.slug)

    def questions_save(self):
        for k, v in self.qform.cleaned_data.items():
            field = self.qform.fields[k]
            if field.answer:
                # We already have a cached answer object, so we don't
                # have to create a new one
                if v == '':
                    # TODO: Deleting the answer removes the option to have a log here.
                    # Maybe setting the answer to '' is the right way to go.
                    field.answer.delete()
                else:
                    self._save_to_answer(field, field.answer, v)
                    field.answer.save()
            elif v != '':
                answer = Answer(
                    submission=self.object,
                    question=field.question,
                )
                self._save_to_answer(field, answer, v)
                answer.save()

    def _save_to_answer(self, field, answer, value):
        action = 'pretalx.submission.answer' + ('update' if answer.pk else 'create')
        if isinstance(field, forms.ModelMultipleChoiceField):
            answstr = ', '.join([str(o) for o in value])
            if not answer.pk:
                answer.save()
            else:
                answer.options.clear()
            answer.answer = answstr
            answer.options.add(*value)
        elif isinstance(field, forms.ModelChoiceField):
            if not answer.pk:
                answer.save()
            else:
                answer.options.clear()
            answer.options.add(value)
            answer.answer = value.answer
        else:
            answer.answer = value
        answer.log_action(action, person=self.request.user, data={'answer': value})
