from django.contrib import messages
from django.db import models, transaction
from django.db.models.deletion import ProtectedError
from django.forms.models import inlineformset_factory
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import ListView, TemplateView, UpdateView, View

from pretalx.common.forms import I18nFormSet
from pretalx.common.mixins.views import ActionFromUrl, PermissionRequired
from pretalx.common.views import CreateOrUpdateView
from pretalx.orga.forms import CfPForm, QuestionForm, SubmissionTypeForm
from pretalx.orga.forms.cfp import AnswerOptionForm, CfPSettingsForm
from pretalx.person.forms import SpeakerFilterForm
from pretalx.submission.models import (
    AnswerOption, CfP, Question, QuestionTarget, SubmissionType,
)


class CfPTextDetail(PermissionRequired, ActionFromUrl, UpdateView):
    form_class = CfPForm
    model = CfP
    template_name = 'orga/cfp/text.html'
    permission_required = 'orga.edit_cfp'
    write_permission_required = 'orga.edit_cfp'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['sform'] = self.sform
        return context

    @cached_property
    def sform(self):
        return CfPSettingsForm(
            read_only=(self._action == 'view'),
            locales=self.request.event.locales,
            obj=self.request.event,
            attribute_name='settings',
            data=self.request.POST if self.request.method == 'POST' else None,
            prefix='settings',
        )

    def get_object(self):
        return self.request.event.cfp

    @cached_property
    def object(self):
        return self.get_object()

    def get_success_url(self) -> str:
        return self.object.urls.text

    def form_valid(self, form):
        if not self.sform.is_valid():
            messages.error(self.request, _('We had trouble saving your input.'))
            return self.form_invalid(form)
        messages.success(self.request, 'The CfP update has been saved.')
        form.instance.event = self.request.event
        result = super().form_valid(form)
        if form.has_changed():
            form.instance.log_action(
                'pretalx.cfp.update', person=self.request.user, orga=True
            )
        self.sform.save()
        return result


class CfPQuestionList(PermissionRequired, TemplateView):
    template_name = 'orga/cfp/question_view.html'
    permission_required = 'orga.view_question'

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['questions'] = Question.all_objects.filter(event=self.request.event)
        return context


class CfPQuestionDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = Question
    form_class = QuestionForm
    permission_required = 'orga.edit_question'
    write_permission_required = 'orga.edit_question'

    def get_template_names(self):
        action = self.request.path.lstrip('/').rpartition('/')[2]
        if action in ('edit', 'new'):
            return 'orga/cfp/question_form.html'
        return 'orga/cfp/question_detail.html'

    def get_permission_object(self):
        return self.object or self.request.event

    def get_object(self) -> Question:
        return Question.all_objects.filter(
            event=self.request.event, pk=self.kwargs.get('pk')
        ).first()

    @cached_property
    def object(self):
        return self.get_object()

    @cached_property
    def formset(self):
        formset_class = inlineformset_factory(
            Question,
            AnswerOption,
            form=AnswerOptionForm,
            formset=I18nFormSet,
            can_delete=True,
            extra=0,
        )
        return formset_class(
            self.request.POST if self.request.method == 'POST' else None,
            queryset=AnswerOption.objects.filter(question=self.object)
            if self.object
            else AnswerOption.objects.none(),
            event=self.request.event,
        )

    def save_formset(self, obj):
        if self.formset.is_valid():
            for form in self.formset.initial_forms:
                if form in self.formset.deleted_forms:
                    if not form.instance.pk:
                        continue
                    obj.log_action(
                        'pretalx.question.option.delete',
                        person=self.request.user,
                        orga=True,
                        data={'id': form.instance.pk},
                    )
                    form.instance.delete()
                    form.instance.pk = None
                elif form.has_changed():
                    form.instance.question = obj
                    form.save()
                    change_data = {
                        k: form.cleaned_data.get(k) for k in form.changed_data
                    }
                    change_data['id'] = form.instance.pk
                    obj.log_action(
                        'pretalx.question.option.update',
                        person=self.request.user,
                        orga=True,
                        data=change_data,
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
                    'pretalx.question.option.create',
                    person=self.request.user,
                    orga=True,
                    data=change_data,
                )

            return True
        return False

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        question = self.object
        context['formset'] = self.formset
        context['filter_form'] = SpeakerFilterForm()
        context['question'] = question
        if question:
            role = self.request.GET.get('role')
            if role == 'true':
                talks = self.request.event.talks.all()
                speakers = self.request.event.speakers.all()
                answers = context['question'].answers.filter(
                    models.Q(person__in=speakers) | models.Q(submission__in=talks)
                )
            elif role == 'false':
                talks = self.request.event.submissions.exclude(
                    code__in=self.request.event.talks.values_list('code', flat=True)
                )
                speakers = self.request.event.submitters.exclude(
                    code__in=self.request.event.speakers.all().values_list(
                        'code', flat=True
                    )
                )
                answers = context['question'].answers.filter(
                    models.Q(person__in=speakers) | models.Q(submission__in=talks)
                )
            else:
                answers = context['question'].answers.all()
            context['answer_count'] = answers.count()
            context['missing_answers'] = (
                question.missing_answers()
                if not role
                else question.missing_answers(
                    filter_speakers=speakers, filter_talks=talks
                )
            )
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if not self.object:
            initial = kwargs['initial'] or dict()
            initial['target'] = self.request.GET.get('type')
            kwargs['initial'] = initial
        return kwargs

    def get_success_url(self) -> str:
        question = self.object or self.instance
        return question.urls.base

    @transaction.atomic
    def form_valid(self, form):
        form.instance.event = self.request.event
        self.instance = form.instance
        result = super().form_valid(form)
        if form.cleaned_data.get('variant') in ('choices', 'multiple_choice'):
            formset = self.save_formset(self.instance)
            if not formset:
                return self.get(self.request, *self.args, **self.kwargs)
        if form.has_changed():
            action = 'pretalx.question.' + ('update' if self.object else 'create')
            form.instance.log_action(action, person=self.request.user, orga=True)
        messages.success(self.request, 'The question has been saved.')
        return result


class CfPQuestionDelete(PermissionRequired, View):
    permission_required = 'orga.remove_question'

    def get_object(self) -> Question:
        return get_object_or_404(
            Question.all_objects, event=self.request.event, pk=self.kwargs.get('pk')
        )

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        question = self.get_object()

        try:
            with transaction.atomic():
                question.options.all().delete()
                question.logged_actions().delete()
                question.delete()
                request.event.log_action(
                    'pretalx.question.delete', person=self.request.user, orga=True
                )
                messages.success(request, _('The question has been deleted.'))
        except ProtectedError:
            question.active = False
            question.save()
            messages.error(
                request,
                _(
                    'You cannot delete a question that has already been answered. We have deactivated the question instead.'
                ),
            )
        return redirect(self.request.event.cfp.urls.questions)


def question_move(request, pk, up=True):
    """
    This is a helper function to avoid duplicating code in question_move_up and
    question_move_down. It takes a question and a direction and then tries to bring
    all items for this question in a new order.
    """
    try:
        question = request.event.questions.get(pk=pk)
    except Question.DoesNotExist:
        raise Http404(_('The selected question does not exist.'))
    if not request.user.has_perm('orga.edit_question', question):
        messages.error(_('Sorry, you are not allowed to reorder questions.'))
        return
    questions = list(request.event.questions.order_by('position'))

    index = questions.index(question)
    if index != 0 and up:
        questions[index - 1], questions[index] = questions[index], questions[index - 1]
    elif index != len(questions) - 1 and not up:
        questions[index + 1], questions[index] = questions[index], questions[index + 1]

    for i, qt in enumerate(questions):
        if qt.position != i:
            qt.position = i
            qt.save()
    messages.success(request, _('The order of questions has been updated.'))


def question_move_up(request, event, pk):
    question_move(request, pk, up=True)
    return redirect(request.event.cfp.urls.questions)


def question_move_down(request, event, pk):
    question_move(request, pk, up=False)
    return redirect(request.event.cfp.urls.questions)


class CfPQuestionToggle(PermissionRequired, View):
    permission_required = 'orga.edit_question'

    def get_object(self) -> Question:
        return Question.all_objects.filter(
            event=self.request.event, pk=self.kwargs.get('pk')
        ).first()

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        question = self.get_object()

        question.active = not question.active
        question.save(update_fields=['active'])
        return redirect(question.urls.base)


class CfPQuestionRemind(PermissionRequired, TemplateView):
    template_name = 'orga/cfp/question_remind.html'
    permission_required = 'orga.view_question'

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['filter_form'] = self.filter_form
        return context

    @cached_property
    def filter_form(self):
        data = self.request.GET if self.request.method == 'GET' else self.request.POST
        return SpeakerFilterForm(data)

    def get_missing_answers(self, *, questions, person, submissions):
        missing = list()
        submissions = submissions.filter(speakers__in=[person])
        for question in questions:
            if question.target == QuestionTarget.SUBMISSION:
                for submission in submissions:
                    if not question.answers.filter(submission=submission):
                        missing.append(question)
                        continue
            elif question.target == QuestionTarget.SPEAKER:
                if not question.answers.filter(person=person):
                    missing.append(question)
        return missing

    def post(self, request, *args, **kwargs):
        if not self.filter_form.is_valid():
            messages.error(request, _('Could not send mails, error in configuration.'))
            return redirect(request.path)
        if not getattr(request.event, 'question_template', None):
            request.event._build_initial_data()
        if self.filter_form.cleaned_data['role'] == 'true':
            people = set(request.event.speakers)
            submissions = request.event.talks
        elif self.filter_form.cleaned_data['role'] == 'false':
            people = set(request.event.submitters) - set(request.event.speakers)
            submissions = request.event.submissions.exclude(
                code__in=request.event.talks.values_list('code', flat=True)
            )
        else:
            people = set(request.event.submitters)
            submissions = request.event.submissions.all()

        mandatory_questions = request.event.questions.filter(required=True)
        context = {
            'url': request.event.urls.user_submissions.full(),
            'event_name': request.event.name,
        }
        for person in people:
            missing = self.get_missing_answers(
                questions=mandatory_questions, person=person, submissions=submissions
            )
            if missing:
                context['questions'] = '\n'.join(
                    [f'- {question.question}' for question in missing]
                )
                request.event.question_template.to_mail(
                    person, event=request.event, context=context
                )
        return redirect(request.event.orga_urls.outbox)


class SubmissionTypeList(PermissionRequired, ListView):
    template_name = 'orga/cfp/submission_type_view.html'
    context_object_name = 'types'
    permission_required = 'orga.view_submission_type'

    def get_permission_object(self):
        return self.request.event

    def get_queryset(self):
        return self.request.event.submission_types.all()


class SubmissionTypeDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = SubmissionType
    form_class = SubmissionTypeForm
    template_name = 'orga/cfp/submission_type_form.html'
    permission_required = 'orga.edit_submission_type'
    write_permission_required = 'orga.edit_submission_type'

    def get_success_url(self) -> str:
        return self.request.event.cfp.urls.types

    def get_object(self):
        return self.request.event.submission_types.filter(
            pk=self.kwargs.get('pk')
        ).first()

    def get_permission_object(self):
        return self.get_object() or self.request.event

    def form_valid(self, form):
        messages.success(self.request, 'The Submission Type has been saved.')
        form.instance.event = self.request.event
        result = super().form_valid(form)
        if form.has_changed():
            action = 'pretalx.submission_type.' + (
                'update' if self.object else 'create'
            )
            form.instance.log_action(action, person=self.request.user, orga=True)
        return result


class SubmissionTypeDefault(PermissionRequired, View):
    permission_required = 'orga.edit_submission_type'

    def get_object(self):
        return get_object_or_404(
            self.request.event.submission_types, pk=self.kwargs.get('pk')
        )

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission_type = self.get_object()
        self.request.event.cfp.default_type = submission_type
        self.request.event.cfp.save(update_fields=['default_type'])
        submission_type.log_action(
            'pretalx.submission_type.make_default', person=self.request.user, orga=True
        )
        messages.success(request, _('The Submission Type has been made default.'))
        return redirect(self.request.event.cfp.urls.types)


class SubmissionTypeDelete(PermissionRequired, View):
    permission_required = 'orga.remove_submission_type'

    def get_object(self):
        return get_object_or_404(
            self.request.event.submission_types, pk=self.kwargs.get('pk')
        )

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission_type = self.get_object()

        if request.event.submission_types.count() == 1:
            messages.error(
                request,
                _(
                    'You cannot delete the only submission type. Try creating another one first!'
                ),
            )
        elif request.event.cfp.default_type == submission_type:
            messages.error(
                request,
                _(
                    'You cannot delete the default submission type. Make another type default first!'
                ),
            )
        else:
            try:
                submission_type.delete()
                request.event.log_action(
                    'pretalx.submission_type.delete',
                    person=self.request.user,
                    orga=True,
                )
                messages.success(request, _('The Submission Type has been deleted.'))
            except ProtectedError:  # TODO: show which/how many submissions are concerned
                messages.error(
                    request,
                    _(
                        'This Submission Type is in use in a submission and cannot be deleted.'
                    ),
                )
        return redirect(self.request.event.cfp.urls.types)
