from django import forms
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView, UpdateView, DetailView

from pretalx.cfp.forms.submissions import InfoForm, QuestionsForm
from pretalx.cfp.views.event import LoggedInEventPageMixin
from pretalx.submission.models import Submission, Answer, SubmissionStates


class SubmissionsListView(LoggedInEventPageMixin, ListView):
    template_name = 'cfp/event/user_submissions.html'
    context_object_name = 'submissions'

    def get_queryset(self):
        return self.request.event.submissions.filter(speakers__in=[self.request.user])


class SubmissionsWithdrawView(LoggedInEventPageMixin, DetailView):
    template_name = 'cfp/event/user_submission_withdraw.html'
    model = Submission
    context_object_name = "submission"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.state = SubmissionStates.WITHDRAWN
        self.object.save()
        messages.success(self.request, _('Your submission has been withdrawn.'))
        return redirect('cfp:event.user.submissions', event=self.request.event.slug)

    def get_object(self, queryset=None):
        try:
            return self.request.event.submissions.prefetch_related('answers', 'answers__options').get(
                speakers__in=[self.request.user],
                pk=self.kwargs.get('id')
            )
        except Submission.DoesNotExist:
            raise Http404()


class SubmissionsEditView(LoggedInEventPageMixin, UpdateView):
    template_name = 'cfp/event/user_submission_edit.html'
    model = Submission
    form_class = InfoForm
    context_object_name = "submission"

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
        return self.object.state in (
            SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED, SubmissionStates.SUBMITTED
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['readonly'] = not self.can_edit
        return kwargs

    def form_valid(self, form):
        if self.can_edit:
            form.save()
            self.questions_save()
            messages.success(self.request, _('Your changes have been saved.'))
        return redirect('cfp:event.user.submissions', event=self.request.event.slug)

    def questions_save(self):
        for k, v in self.qform.cleaned_data.items():
            field = self.qform.fields[k]
            if field.answer:
                # We already have a cached answer object, so we don't
                # have to create a new one
                if v == '':
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
        if isinstance(field, forms.ModelMultipleChoiceField):
            answstr = ", ".join([str(o) for o in value])
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
