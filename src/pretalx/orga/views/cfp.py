from csp.decorators import csp_update
from django.contrib import messages
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.forms.models import inlineformset_factory
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView, TemplateView, UpdateView, View

from pretalx.common.forms import I18nFormSet
from pretalx.common.views import ActionFromUrl, CreateOrUpdateView
from pretalx.orga.forms import CfPForm, QuestionForm, SubmissionTypeForm
from pretalx.orga.forms.cfp import AnswerOptionForm, CfPSettingsForm
from pretalx.submission.models import (
    AnswerOption, CfP, Question, SubmissionType,
)


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


class CfPQuestionList(TemplateView):
    template_name = 'orga/cfp/question_view.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['speaker_questions'] = self.request.event.questions.filter(target='speaker')
        ctx['submission_questions'] = self.request.event.questions.filter(target='submission')
        return ctx


@method_decorator(csp_update(SCRIPT_SRC="'self' 'unsafe-inline'"), name='dispatch')
class CfPQuestionDetail(ActionFromUrl, CreateOrUpdateView):
    model = Question
    form_class = QuestionForm
    template_name = 'orga/cfp/question_form.html'

    def get_object(self) -> Question:
        return self.request.event.questions.filter(pk=self.kwargs.get('pk')).first()

    @cached_property
    def formset(self):
        formset_class = inlineformset_factory(
            Question, AnswerOption, form=AnswerOptionForm, formset=I18nFormSet,
            can_delete=True, extra=0,
        )
        return formset_class(
            self.request.POST if self.request.method == 'POST' else None,
            queryset=AnswerOption.objects.filter(question=self.get_object()) if self.get_object() else AnswerOption.objects.none(),
            event=self.request.event
        )

    def save_formset(self, obj):
        if self.formset.is_valid():
            for form in self.formset.initial_forms:
                if form in self.formset.deleted_forms:
                    if not form.instance.pk:
                        continue
                    obj.log_action(
                        'pretalx.event.question.option.deleted', person=self.request.user, orga=True, data={
                            'id': form.instance.pk
                        }
                    )
                    form.instance.delete()
                    form.instance.pk = None
                elif form.has_changed():
                    form.instance.question = obj
                    form.save()
                    change_data = {k: form.cleaned_data.get(k) for k in form.changed_data}
                    change_data['id'] = form.instance.pk
                    obj.log_action(
                        'pretalx.event.question.option.changed',
                        person=self.request.user, orga=True, data=change_data
                    )

            for form in self.formset.extra_forms:
                if not form.has_changed():
                    continue
                if self.formset._should_delete_form(form):
                    continue
                form.instance.question = obj
                form.save()
                change_data = {k: form.cleaned_data.get(k) for k in form.changed_data}
                change_data['id'] = form.instance.pk
                obj.log_action(
                    'pretalx.event.question.option.added',
                    person=self.request.user, orga=True, data=change_data
                )

            return True
        return False

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['formset'] = self.formset
        return ctx

    def get_success_url(self) -> str:
        obj = self.get_object() or self.instance
        return obj.urls.base

    @transaction.atomic
    def form_valid(self, form):
        form.instance.event = self.request.event
        self.instance = form.instance
        ret = super().form_valid(form)
        if form.cleaned_data.get('variant') in ('choices', 'multiple_choice'):
            result = self.save_formset(self.instance)
            if not result:
                return self.get(self.request, *self.args, **self.kwargs)
        if form.has_changed():
            action = 'pretalx.question.' + ('update' if self.object else 'create')
            form.instance.log_action(action, person=self.request.user, orga=True)
        messages.success(self.request, 'The question has been saved.')
        return ret


class CfPQuestionDelete(View):

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        question = self.request.event.questions.get(pk=self.kwargs.get('pk'))

        try:
            question.delete()
            question.log_action('pretalx.question.delete', person=self.request.user, orga=True)
            messages.success(request, _('The question has been deleted.'))
        except ProtectedError:
            messages.error(request, _('You cannot delete a question that has already been answered.'))
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
