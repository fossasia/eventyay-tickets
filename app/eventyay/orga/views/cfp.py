import json
import logging
from collections import defaultdict

from csp.decorators import csp_update
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.forms.models import inlineformset_factory
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView, UpdateView, View
from django_context_decorator import context

from eventyay.cfp.flow import CfPFlow
from eventyay.common.forms import I18nFormSet
from eventyay.common.text.phrases import phrases
from eventyay.common.text.serialize import I18nStrJSONEncoder
from eventyay.common.views.generic import OrgaCRUDView
from eventyay.common.views.mixins import (
    ActionFromUrl,
    EventPermissionRequired,
    OrderActionMixin,
    PermissionRequired,
)
from eventyay.base.models import MailTemplateRoles
from eventyay.orga.forms import CfPForm, TalkQuestionForm, SubmissionTypeForm, TrackForm
from eventyay.orga.forms.cfp import (
    AccessCodeSendForm,
    AnswerOptionForm,
    CfPSettingsForm,
    QuestionFilterForm,
    ReminderFilterForm,
    SubmitterAccessCodeForm,
)
from eventyay.base.models import (
    AnswerOption,
    CfP,
    TalkQuestion,
    TalkQuestionTarget,
    SubmissionType,
    SubmitterAccessCode,
    Track,
)
from eventyay.talk_rules.submission import questions_for_user

logger = logging.getLogger(__name__)


class CfPTextDetail(PermissionRequired, ActionFromUrl, UpdateView):
    form_class = CfPForm
    model = CfP
    template_name = 'orga/cfp/text.html'
    permission_required = 'base.update_event'
    write_permission_required = 'base.update_event'

    @context
    def tablist(self):
        return {
            'general': _('General information'),
            'fields': _('Fields'),
        }

    @context
    @cached_property
    def sform(self):
        return CfPSettingsForm(
            read_only=(self.action == 'view'),
            locales=self.request.event.locales,
            obj=self.request.event,
            data=self.request.POST if self.request.method == 'POST' else None,
            prefix='settings',
        )

    @context
    @cached_property
    def different_deadlines(self):
        deadlines = defaultdict(list)
        for session_type in self.request.event.submission_types.filter(deadline__isnull=False):
            deadlines[session_type.deadline].append(session_type)
        deadlines.pop(self.request.event.cfp.deadline, None)
        if deadlines:
            return dict(deadlines)

    def get_object(self, queryset=None):
        return self.request.event.cfp

    def get_success_url(self) -> str:
        return self.object.urls.text

    @transaction.atomic
    def form_valid(self, form):
        if not self.sform.is_valid():
            messages.error(self.request, phrases.base.error_saving_changes)
            return self.form_invalid(form)
        messages.success(self.request, phrases.base.saved)
        form.instance.event = self.request.event
        result = super().form_valid(form)
        if form.has_changed():
            form.instance.log_action('eventyay.cfp.update', person=self.request.user, orga=True)
        self.sform.save()
        return result


class QuestionView(OrderActionMixin, OrgaCRUDView):
    model = TalkQuestion
    form_class = TalkQuestionForm
    template_namespace = 'orga/cfp'
    context_object_name = 'question'
    detail_is_update = False

    def get_queryset(self):
        return (
            questions_for_user(self.request.event, self.request.user)
            .annotate(answer_count=Count('answers'))
            .order_by('position')
        )

    def get_generic_title(self, instance=None):
        if instance:
            return (
                _('Custom field') + f' {phrases.base.quotation_open}{instance.question}{phrases.base.quotation_close}'
            )
        if self.action == 'create':
            return _('New custom field')
        return _('Custom fields')

    def get_permission_required(self):
        permission_map = {'list': 'orga_list', 'detail': 'orga_view'}
        permission = permission_map.get(self.action, self.action)
        return self.model.get_perm(permission)

    @cached_property
    def formset(self):
        formset_class = inlineformset_factory(
            TalkQuestion,
            AnswerOption,
            form=AnswerOptionForm,
            formset=I18nFormSet,
            can_delete=True,
            extra=0,
        )
        return formset_class(
            self.request.POST if self.request.method == 'POST' else None,
            queryset=(
                AnswerOption.objects.filter(question=self.object) if self.object else AnswerOption.objects.none()
            ),
            event=self.request.event,
        )

    def save_formset(self, obj):
        if not self.formset.is_valid():
            return False
        for form in self.formset.initial_forms:
            if form in self.formset.deleted_forms:
                if not form.instance.pk:
                    continue
                obj.log_action(
                    'eventyay.question.option.delete',
                    person=self.request.user,
                    orga=True,
                    data={'id': form.instance.pk},
                )
                form.instance.delete()
                form.instance.pk = None
            elif form.has_changed():
                form.instance.question = obj
                form.save()
                change_data = {key: form.cleaned_data.get(key) for key in form.changed_data}
                change_data['id'] = form.instance.pk
                obj.log_action(
                    'eventyay.question.option.update',
                    person=self.request.user,
                    orga=True,
                    data=change_data,
                )

        extra_forms = [
            form for form in self.formset.extra_forms if form.has_changed and not self.formset._should_delete_form(form)
        ]
        for form in extra_forms:
            form.instance.question = obj
            form.save()
            change_data = {key: form.cleaned_data.get(key) for key in form.changed_data}
            change_data['id'] = form.instance.pk
            obj.log_action(
                'eventyay.question.option.create',
                person=self.request.user,
                orga=True,
                data=change_data,
            )

        return True

    @cached_property
    def filter_form(self):
        return QuestionFilterForm(self.request.GET, event=self.request.event)

    @cached_property
    def base_search_url(self):
        if not self.object or self.object.target == 'reviewer':
            return
        role = self.request.GET.get('role') or ''
        track = self.request.GET.get('track') or ''
        submission_type = self.request.GET.get('submission_type') or ''
        if self.object.target == 'submission':
            url = self.request.event.orga_urls.submissions + '?'
            if role == 'accepted':
                url = f'{url}state=accepted&state=confirmed&'
            elif role == 'confirmed':
                url = f'{url}state=confirmed&'
            if track:
                url = f'{url}track={track}&'
            if submission_type:
                url = f'{url}submission_type={submission_type}&'
        else:
            url = self.request.event.orga_urls.speakers + '?'
        return f'{url}&question={self.object.id}&'

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        if not self.object or not self.filter_form.is_valid():
            return result
        result.update(self.filter_form.get_question_information(self.object))
        result['grouped_answers_json'] = json.dumps(list(result['grouped_answers']), cls=I18nStrJSONEncoder)
        if self.action == 'detail':
            result['base_search_url'] = self.base_search_url
            result['filter_form'] = self.filter_form
        if 'form' in result:
            result['formset'] = self.formset
        return result

    def form_valid(self, form):
        form.instance.event = self.request.event
        self.instance = form.instance
        if form.cleaned_data.get('variant') in ('choices', 'multiple_choice'):
            changed_options = [form.changed_data for form in self.formset if form.has_changed()]
            if form.cleaned_data.get('options') and changed_options:
                messages.error(
                    self.request,
                    _('You cannot change the options and upload an option file at the same time.'),
                )
                return self.form_invalid(form)
        result = super().form_valid(form)
        if form.cleaned_data.get('variant') in (
            'choices',
            'multiple_choice',
        ) and not form.cleaned_data.get('options'):
            formset = self.save_formset(self.instance)
            if not formset:
                return self.get(self.request, *self.args, **self.kwargs)
        return result

    def post(self, request, *args, **kwargs):
        order = request.POST.get('order')
        if not order:
            return super().post(request, *args, **kwargs)
        order = order.split(',')
        for index, pk in enumerate(order):
            option = get_object_or_404(
                self.object.options,
                pk=pk,
            )
            option.position = index
            option.save(update_fields=['position'])
        return self.get(request, *args, **kwargs)

    def perform_delete(self):
        try:
            with transaction.atomic():
                self.object.options.all().delete()
                self.object.logged_actions().delete()
                super().perform_delete()
        except ProtectedError:
            self.object.active = False
            self.object.save()
            messages.error(
                self.request,
                _('You cannot delete a custom field that has any responses. We have deactivated the field instead.'),
            )


class CfPQuestionToggle(PermissionRequired, View):
    permission_required = 'base.update_talkquestion'

    def get_object(self) -> TalkQuestion:
        return TalkQuestion.all_objects.filter(event=self.request.event, pk=self.kwargs.get('pk')).first()

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        question = self.get_object()

        question.active = not question.active
        question.save(update_fields=['active'])
        return redirect(question.urls.base)


class CfPQuestionRemind(EventPermissionRequired, FormView):
    template_name = 'orga/cfp/question/remind.html'
    permission_required = 'base.orga_view_talkquestion'
    form_class = ReminderFilterForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    @staticmethod
    def get_missing_answers(*, questions, person, submissions):
        missing = []
        submissions = submissions.filter(speakers__in=[person])
        for question in questions:
            if question.target == TalkQuestionTarget.SUBMISSION:
                for submission in submissions:
                    answer = question.answers.filter(submission=submission).first()
                    if not answer or not answer.is_answered:
                        missing.append(question)
            elif question.target == TalkQuestionTarget.SPEAKER:
                answer = question.answers.filter(person=person).first()
                if not answer or not answer.is_answered:
                    missing.append(question)
        return missing

    @context
    def reminder_template(self):
        return self.request.event.get_mail_template(MailTemplateRoles.QUESTION_REMINDER)

    def form_invalid(self, form):
        messages.error(self.request, _('Could not send mails, error in configuration.'))
        return super().form_invalid(form)

    def form_valid(self, form):
        submissions = form.get_submissions()
        people = self.request.event.submitters.filter(submissions__in=submissions)
        questions = form.cleaned_data['questions'] or form.get_question_queryset()
        data = {
            'url': self.request.event.urls.user_submissions.full(),
        }
        for person in people:
            missing = self.get_missing_answers(questions=questions, person=person, submissions=submissions)
            if missing:
                data['questions'] = '\n'.join(f'- {question.question}' for question in missing)
                self.request.event.get_mail_template(MailTemplateRoles.QUESTION_REMINDER).to_mail(
                    person,
                    event=self.request.event,
                    context=data,
                    context_kwargs={'user': person},
                )
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.event.orga_urls.outbox


class SubmissionTypeView(OrderActionMixin, OrgaCRUDView):
    model = SubmissionType
    form_class = SubmissionTypeForm
    template_namespace = 'orga/cfp'

    def get_queryset(self):
        return self.request.event.submission_types.all().order_by('default_duration')

    def get_permission_required(self):
        permission_map = {'list': 'orga_list', 'detail': 'orga_detail'}
        permission = permission_map.get(self.action, self.action)
        return self.model.get_perm(permission)

    def get_generic_title(self, instance=None):
        if instance:
            return _('Session type') + f' {phrases.base.quotation_open}{instance.name}{phrases.base.quotation_close}'
        if self.action == 'create':
            return _('New Session Type')
        return _('Session types')

    def delete_handler(self, request, *args, **kwargs):
        try:
            return super().delete_handler(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                _('This Session Type is in use in a proposal and cannot be deleted.'),
            )
            return self.delete_view(request, *args, **kwargs)


class SubmissionTypeDefault(PermissionRequired, View):
    permission_required = 'base.update_submissiontype'

    def get_object(self):
        return get_object_or_404(self.request.event.submission_types, pk=self.kwargs.get('pk'))

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission_type = self.get_object()
        self.request.event.cfp.default_type = submission_type
        self.request.event.cfp.save(update_fields=['default_type'])
        submission_type.log_action('eventyay.submission_type.make_default', person=self.request.user, orga=True)
        messages.success(request, _('The Session Type has been made default.'))
        return redirect(self.request.event.cfp.urls.types)


class TrackView(OrderActionMixin, OrgaCRUDView):
    model = Track
    form_class = TrackForm
    template_namespace = 'orga/cfp'

    def get_queryset(self):
        return self.request.event.tracks.all()

    def get_permission_required(self):
        permission_map = {'list': 'orga_list', 'detail': 'orga_view'}
        permission = permission_map.get(self.action, self.action)
        return self.model.get_perm(permission)

    def get_generic_title(self, instance=None):
        if instance:
            return _('Track') + f' {phrases.base.quotation_open}{instance.name}{phrases.base.quotation_close}'
        if self.action == 'create':
            return _('New track')
        return _('Tracks')

    def delete_handler(self, request, *args, **kwargs):
        try:
            return super().delete_handler(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                _('This track is in use in a proposal and cannot be deleted.'),
            )
            return self.delete_view(request, *args, **kwargs)


class AccessCodeView(OrderActionMixin, OrgaCRUDView):
    model = SubmitterAccessCode
    form_class = SubmitterAccessCodeForm
    template_namespace = 'orga/cfp'
    context_object_name = 'access_code'
    lookup_field = 'code'
    path_converter = 'str'

    def get_queryset(self):
        return self.request.event.submitter_access_codes.all().order_by('valid_until')

    def get_generic_title(self, instance=None):
        if instance:
            return _('Access code') + f' {phrases.base.quotation_open}{instance.code}{phrases.base.quotation_close}'
        if self.action == 'create':
            return _('New access code')
        return _('Access codes')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if track := self.request.GET.get('track'):
            if track := self.request.event.tracks.filter(pk=track).first():
                kwargs['initial'] = kwargs.get('initial', {})
                kwargs['initial']['track'] = track
        return kwargs

    def delete_handler(self, request, *args, **kwargs):
        try:
            return super().delete_handler(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                _(
                    'This access code has been used for a proposal and cannot be deleted. To disable it, you can set its validity date to the past.'
                ),
            )
            return self.delete_view(request, *args, **kwargs)


class AccessCodeSend(PermissionRequired, UpdateView):
    model = SubmitterAccessCode
    form_class = AccessCodeSendForm
    context_object_name = 'access_code'
    template_name = 'orga/cfp/submitteraccesscode/send.html'
    permission_required = 'base.view_submitteraccesscode'

    def get_success_url(self) -> str:
        return self.request.event.cfp.urls.access_codes

    def get_object(self):
        return self.request.event.submitter_access_codes.filter(code__iexact=self.kwargs.get('code')).first()

    def get_permission_object(self):
        return self.get_object()

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result['user'] = self.request.user
        return result

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, _('The access code has been sent.'))
        code = self.get_object()
        code.log_action(
            'eventyay.access_code.send',
            person=self.request.user,
            orga=True,
            data={'email': form.cleaned_data['to']},
        )
        return result

@method_decorator(csp_update({'SCRIPT_SRC': "'self' 'unsafe-eval'"}), name='dispatch')
class CfPFlowEditor(EventPermissionRequired, TemplateView):
    template_name = 'orga/cfp/flow.html'
    permission_required = 'base.update_event'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_configuration'] = self.request.event.cfp_flow.get_editor_config(json_compat=True)
        ctx['event_configuration'] = {
            'header_pattern': self.request.event.display_settings['header_pattern'] or 'bg-primary',
            'header_image': (self.request.event.header_image.url if self.request.event.header_image else None),
            'logo_image': (self.request.event.logo.url if self.request.event.logo else None),
            'primary_color': self.request.event.visible_primary_color,
            'locales': self.request.event.locales,
        }
        return ctx

    def post(self, request, *args, **kwargs):
        # TODO: Improve validation
        try:
            data = json.loads(request.body.decode())
        except json.JSONDecodeError as e:
            logger.warning('Request body is not JSON: %s', e)
            return JsonResponse({'error': 'Invalid data'}, status=400)

        flow = CfPFlow(self.request.event)
        if 'action' in data and data['action'] == 'reset':
            flow.reset()
        else:
            logger.debug('Saving new CfP flow configuration: %s', data)
            flow.save_config(data)
        return JsonResponse({'success': True})
