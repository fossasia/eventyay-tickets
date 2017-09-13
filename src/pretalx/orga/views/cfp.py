from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView, UpdateView, View

from pretalx.common.views import ActionFromUrl, CreateOrUpdateView
from pretalx.orga.forms import CfPForm, QuestionForm, SubmissionTypeForm
from pretalx.orga.forms.cfp import CfPSettingsForm
from pretalx.submission.models import CfP, Question, SubmissionType


class CfPTextDetail(ActionFromUrl, UpdateView):
    form_class = CfPForm
    model = CfP
    template_name = 'orga/cfp/text.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['sform'] = self.sform
        return ctx

    @cached_property
    def sform(self):
        return CfPSettingsForm(
            read_only=(self._action == 'view'),
            locales=self.request.event.locales,
            obj=self.request.event,
            attribute_name='settings',
            data=self.request.POST if self.request.method == "POST" else None,
            prefix='settings'
        )

    def get_object(self):
        return self.request.event.cfp

    def get_success_url(self) -> str:
        return self.get_object().urls.text

    def form_valid(self, form):
        if not self.sform.is_valid():
            return self.form_invalid(form)
        messages.success(self.request, 'The CfP update has been saved.')
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        if form.has_changed():
            form.instance.log_action('pretalx.cfp.update', person=self.request.user, orga=True)
        self.sform.save()
        return ret


class CfPQuestionList(ListView):
    template_name = 'orga/cfp/question_view.html'
    context_object_name = 'questions'

    def get_queryset(self):
        return self.request.event.questions.all()


class CfPQuestionDetail(ActionFromUrl, CreateOrUpdateView):
    model = Question
    form_class = QuestionForm
    template_name = 'orga/cfp/question_form.html'

    def get_object(self) -> Question:
        return self.request.event.questions.get(pk=self.kwargs.get('pk'))

    def get_success_url(self) -> str:
        return self.request.event.cfp.urls.questions

    def form_valid(self, form):
        messages.success(self.request, 'The question has been saved.')
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        if form.has_changed():
            action = 'pretalx.question.' + ('update' if self.object else 'create')
            form.instance.log_action(action, person=self.request.user, orga=True)
        return ret


class CfPQuestionDelete(View):

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)

        question = self.request.event.questions.get(pk=self.kwargs.get('pk'))
        question.log_action('pretalx.question.delete', person=self.request.user, orga=True)
        question.delete()
        messages.success(request, _('The question has been deleted.'))
        return redirect(self.request.event.cfp.urls.questions)


class SubmissionTypeList(ListView):
    template_name = 'orga/cfp/submission_type_view.html'
    context_object_name = 'types'

    def get_queryset(self):
        return self.request.event.submission_types.all()


class SubmissionTypeDetail(ActionFromUrl, CreateOrUpdateView):
    model = SubmissionType
    form_class = SubmissionTypeForm
    template_name = 'orga/cfp/submission_type_form.html'

    def get_success_url(self) -> str:
        return self.request.event.cfp.urls.types

    def get_object(self):
        return self.request.event.submission_types.get(pk=self.kwargs.get('pk'))

    def form_valid(self, form):
        messages.success(self.request, 'The Submission Type has been saved.')
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        if form.has_changed():
            action = 'pretalx.submission_type.' + ('update' if self.object else 'create')
            form.instance.log_action(action, person=self.request.user, orga=True)
        return ret


class SubmissionTypeDefault(View):

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)

        submission_type = self.request.event.submission_types.get(pk=self.kwargs.get('pk'))
        self.request.event.cfp.default_type = submission_type
        self.request.event.cfp.save(update_fields=['default_type'])
        submission_type.log_action('pretalx.submission_type.make_default', person=self.request.user, orga=True)
        messages.success(request, _('The Submission Type has been made default.'))
        return redirect(self.request.event.cfp.urls.types)


class SubmissionTypeDelete(View):

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission_type = self.request.event.submission_types.get(pk=self.kwargs.get('pk'))

        if request.event.submission_types.count() == 1:
            messages.error(request, _('You cannot delete the only submission type. Try creating another one first!'))
        elif request.event.cfp.default_type == submission_type:
            messages.error(request, _('You cannot delete the default submission type. Make another type default first!'))
        else:
            try:
                submission_type.delete()
                request.event.log_action('pretalx.submission_type.delete', person=self.request.user, orga=True)
                messages.success(request, _('The Submission Type has been deleted.'))
            except ProtectedError:  # TODO: show which/how many submissions are concerned
                messages.error(request, _('This Submission Type is in use in a submission and cannot be deleted.'))
        return redirect(self.request.event.cfp.urls.types)
