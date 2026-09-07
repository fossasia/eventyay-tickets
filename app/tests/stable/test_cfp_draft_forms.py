from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django import forms
from django.test import RequestFactory
from django.utils.datastructures import MultiValueDict

from eventyay.base.models import (
    AnswerOption,
    Submission,
    TalkQuestion,
    TalkQuestionRequired,
    TalkQuestionTarget,
    TalkQuestionVariant,
)
from eventyay.cfp.forms.cfp import CfPFormMixin
from eventyay.cfp.flow import BaseCfPStep, GenericFlowStep
from eventyay.cfp.views.user import SubmissionsEditView
from eventyay.common.forms.widgets import SlidesWidget
from eventyay.person.forms import SpeakerProfileForm
from eventyay.submission.forms import InfoForm
from eventyay.submission.forms.submission import AUTO_DRAFT_TITLE
from eventyay.base.models.submission import SubmissionStates


@pytest.fixture(autouse=True)
def _disable_scopes():
    from django_scopes import scopes_disabled
    with scopes_disabled():
        yield


class SizedValue:
    def __init__(self, size):
        self.size = size

    def __len__(self):
        return self.size


class DummyQuestionField:
    def __init__(self, *, initial=None, answer=None):
        self.initial = initial
        self.answer = answer


class DummyFlowStep(GenericFlowStep, BaseCfPStep):
    identifier = 'info'
    _title = ''
    _text = ''


def test_cfp_form_mixin_scrubs_incomplete_errors_in_not_strict_mode():
    class PartialValueField(forms.MultiValueField):
        def __init__(self, *args, **kwargs):
            super().__init__(
                fields=(
                    forms.CharField(required=True),
                    forms.CharField(required=True),
                ),
                require_all_fields=False,
                *args,
                **kwargs,
            )

        def compress(self, data_list):
            return data_list

    class DraftSplitForm(CfPFormMixin, forms.Form):
        availability = PartialValueField(required=True)

    form = DraftSplitForm(
        data={
            'availability_0': '2026-05-26',
            'availability_1': '',
        },
        not_strict=True,
    )

    assert form.is_valid()
    assert not form.errors


def test_slides_widget_accepts_plain_dict_session_data():
    widget = SlidesWidget()

    value = widget.value_from_datadict(data={}, files=MultiValueDict(), name='slides')

    assert value == {
        'resources': [],
        'clear_ids': [],
    }


def test_slides_widget_get_context_re_render():
    widget = SlidesWidget()

    # Normal GET request (None value or list of existing resources)
    ctx1 = widget.get_context('slides', None, {})
    assert ctx1['widget']['is_re_render'] is False

    ctx2 = widget.get_context('slides', [], {})
    assert ctx2['widget']['is_re_render'] is False

    # Initial values from DB (dict with existing_resources)
    ctx3 = widget.get_context('slides', {'existing_resources': []}, {})
    assert ctx3['widget']['is_re_render'] is False

    # Validation error re-render (raw dict from value_from_datadict without database keys)
    ctx4 = widget.get_context('slides', {'links_text': 'http://...', 'clear_ids': []}, {})
    assert ctx4['widget']['is_re_render'] is True



def test_info_form_ignores_default_slot_count_for_drafts():
    assert InfoForm._has_real_draft_value('slot_count', 1) is False
    assert InfoForm._has_real_draft_value('slot_count', 2) is True


def test_info_form_draft_content_check_includes_question_fields():
    assert InfoForm._is_draft_content_field_name('question_23') is True
    assert InfoForm._is_draft_content_field_name('submission_type') is False
    assert InfoForm._is_draft_content_field_name('content_locale') is False
    assert InfoForm._is_draft_content_field_name('description') is True


def test_info_form_ignores_empty_sized_values_for_drafts():
    assert InfoForm._has_real_draft_value('question_12', SizedValue(0)) is False
    assert InfoForm._has_real_draft_value('question_12', SizedValue(1)) is True


def test_submission_display_title_uses_fallback_for_auto_draft_title():
    submission = Submission(title=AUTO_DRAFT_TITLE)

    assert str(submission.display_title) == 'Untitled draft'


def test_submission_display_title_preserves_regular_title():
    submission = Submission(title='Real title')

    assert submission.display_title == 'Real title'


def test_info_form_uses_continue_message_for_blank_partial_continue():
    form = InfoForm.__new__(InfoForm)
    form.draft_save = False

    assert str(form._get_empty_content_error_message()) == 'Please fill at least one field.'


def test_info_form_preserves_auto_draft_title_for_blank_draft_edits():
    form = InfoForm.__new__(InfoForm)
    form.draft_save = True
    form.instance = SimpleNamespace(title=AUTO_DRAFT_TITLE)
    form.cleaned_data = {'title': ''}

    form._preserve_auto_draft_title()

    assert form.cleaned_data['title'] == AUTO_DRAFT_TITLE
    assert form.instance.title == AUTO_DRAFT_TITLE


def test_info_form_keeps_explicit_title_when_editing_draft():
    form = InfoForm.__new__(InfoForm)
    form.draft_save = True
    form.instance = SimpleNamespace(title=AUTO_DRAFT_TITLE)
    form.cleaned_data = {'title': 'Real title'}

    form._preserve_auto_draft_title()

    assert form.cleaned_data['title'] == 'Real title'
    assert form.instance.title == AUTO_DRAFT_TITLE


def test_info_form_restores_sentinel_when_clearing_a_non_empty_draft_title():
    form = InfoForm.__new__(InfoForm)
    form.draft_save = True
    form.instance = SimpleNamespace(title='Previously saved title')
    form.cleaned_data = {'title': ''}

    form._preserve_auto_draft_title()

    assert form.cleaned_data['title'] == AUTO_DRAFT_TITLE
    assert form.instance.title == AUTO_DRAFT_TITLE


def test_question_field_counts_session_roundtrip_content_for_drafts():
    form = InfoForm.__new__(InfoForm)

    assert form._question_field_has_user_content(DummyQuestionField(initial=[]), [1]) is True
    assert form._question_field_has_user_content(DummyQuestionField(initial=[]), []) is False


def test_question_field_ignores_untouched_default_value_for_drafts():
    form = InfoForm.__new__(InfoForm)

    assert form._question_field_has_user_content(DummyQuestionField(initial='default'), 'default') is False


def test_question_field_keeps_existing_answer_as_real_draft_content():
    form = InfoForm.__new__(InfoForm)

    assert form._question_field_has_user_content(DummyQuestionField(initial='default', answer=object()), 'default') is True


def test_submission_edit_view_treats_draft_save_as_non_strict():
    request = RequestFactory().post('/', data={'action': 'draft'})
    view = SubmissionsEditView()
    view.request = request
    view.object = SimpleNamespace(state=SubmissionStates.DRAFT)

    assert view.is_draft_action() is True


def test_submission_edit_view_keeps_dedraft_strict():
    request = RequestFactory().post('/', data={'action': 'dedraft'})
    view = SubmissionsEditView()
    view.request = request
    view.object = SimpleNamespace(state=SubmissionStates.DRAFT)

    assert view.is_draft_action() is False


def test_generic_flow_step_continue_uses_non_strict_without_draft_mode():
    event = SimpleNamespace(cfp_flow=SimpleNamespace(config={'steps': {}}))
    request = RequestFactory().post('/', data={'action': 'submit'})
    request.event = event
    request.resolver_match = SimpleNamespace(kwargs={'step': 'info'})
    step = DummyFlowStep(event)
    step.request = request
    step._next = SimpleNamespace(is_applicable=lambda request: True)

    kwargs = step.get_form_kwargs()

    assert kwargs['not_strict'] is True
    assert kwargs['draft_save'] is False


def test_generic_flow_step_final_submit_stays_strict():
    event = SimpleNamespace(cfp_flow=SimpleNamespace(config={'steps': {}}))
    request = RequestFactory().post('/', data={'action': 'submit'})
    request.event = event
    request.resolver_match = SimpleNamespace(kwargs={'step': 'info'})
    step = DummyFlowStep(event)
    step.request = request

    kwargs = step.get_form_kwargs()

    assert kwargs['not_strict'] is False
    assert kwargs['draft_save'] is False


def test_generic_flow_step_draft_save_enables_draft_mode():
    event = SimpleNamespace(cfp_flow=SimpleNamespace(config={'steps': {}}))
    request = RequestFactory().post('/', data={'action': 'draft'})
    request.event = event
    request.resolver_match = SimpleNamespace(kwargs={'step': 'info'})
    step = DummyFlowStep(event)
    step.request = request

    kwargs = step.get_form_kwargs()

    assert kwargs['not_strict'] is True
    assert kwargs['draft_save'] is True


@pytest.mark.django_db
def test_info_form_hides_auto_draft_title(event):
    submission = Submission(
        event=event,
        title=AUTO_DRAFT_TITLE,
        submission_type=event.cfp.default_type,
        content_locale=event.locale,
    )

    with patch.object(InfoForm, 'inject_questions_into_fields', autospec=True):
        form = InfoForm(event, instance=submission)

    assert form['title'].value() == ''


def test_info_form_save_cleans_before_preserving_auto_draft_title():
    form = InfoForm.__new__(InfoForm)
    form.default_values = {}
    form.draft_save = True
    form.instance = SimpleNamespace(title=AUTO_DRAFT_TITLE)
    form.original_instance_title = AUTO_DRAFT_TITLE
    form._errors = None
    clean_calls = []

    def fake_full_clean():
        clean_calls.append(True)
        form._errors = {}
        form.cleaned_data = {'title': ''}

    form.full_clean = fake_full_clean

    with patch.object(forms.ModelForm, 'save', autospec=True, return_value=form.instance) as mocked_save:
        saved = InfoForm.save(form, commit=False)

    assert clean_calls == [True]
    assert saved is form.instance
    assert form.cleaned_data['title'] == AUTO_DRAFT_TITLE
    assert form.instance.title == AUTO_DRAFT_TITLE
    mocked_save.assert_called_once_with(form, commit=False)


def test_info_form_save_preserves_auto_draft_title_after_validation_mutates_instance():
    form = InfoForm.__new__(InfoForm)
    form.default_values = {}
    form.draft_save = True
    form.original_instance_title = AUTO_DRAFT_TITLE
    form.instance = SimpleNamespace(title='')
    form.cleaned_data = {'title': ''}
    form._errors = {}

    with patch.object(forms.ModelForm, 'save', autospec=True, return_value=form.instance) as mocked_save:
        saved = InfoForm.save(form, commit=False)

    assert saved is form.instance
    assert form.cleaned_data['title'] == AUTO_DRAFT_TITLE
    assert form.instance.title == AUTO_DRAFT_TITLE
    mocked_save.assert_called_once_with(form, commit=False)


@pytest.mark.django_db
def test_info_form_requires_real_content_for_drafts(event):
    form = InfoForm(
        event,
        data={
            'title': AUTO_DRAFT_TITLE,
            'submission_type': event.cfp.default_type.pk,
            'content_locale': event.locale,
            'slot_count': 1,
        },
        not_strict=True,
        draft_save=True,
    )

    assert not form.is_valid()
    assert form.non_field_errors() == ['Please fill at least one field.']


@pytest.mark.django_db
def test_info_form_ignores_empty_checkbox_question_for_drafts(event):
    question = TalkQuestion.all_objects.create(
        event=event,
        question='Session format',
        variant=TalkQuestionVariant.MULTIPLE,
        target=TalkQuestionTarget.SUBMISSION,
        question_required=TalkQuestionRequired.OPTIONAL,
        contains_personal_data=False,
        position=1,
    )
    AnswerOption.objects.create(question=question, answer='Workshop')

    form = InfoForm(
        event,
        data={
            'title': AUTO_DRAFT_TITLE,
            'submission_type': event.cfp.default_type.pk,
            'content_locale': event.locale,
            'slot_count': 1,
        },
        not_strict=True,
        draft_save=True,
    )

    assert not form.is_valid()
    assert form.non_field_errors() == ['Please fill at least one field.']


@pytest.mark.django_db
def test_info_form_allows_checked_checkbox_question_for_drafts(event):
    question = TalkQuestion.all_objects.create(
        event=event,
        question='Session format',
        variant=TalkQuestionVariant.MULTIPLE,
        target=TalkQuestionTarget.SUBMISSION,
        question_required=TalkQuestionRequired.OPTIONAL,
        contains_personal_data=False,
        position=1,
    )
    option = AnswerOption.objects.create(question=question, answer='Workshop')

    form = InfoForm(
        event,
        data={
            'title': AUTO_DRAFT_TITLE,
            'submission_type': event.cfp.default_type.pk,
            'content_locale': event.locale,
            'slot_count': 1,
            f'question_{question.pk}': [str(option.pk)],
        },
        not_strict=True,
        draft_save=True,
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_speaker_profile_form_not_strict_allows_missing_required_fields(event, user):
    event.cfp.fields['avatar']['visibility'] = 'required'
    event.cfp.save()

    form = SpeakerProfileForm(
        data={
            'fullname': '',
            'email': '',
            'biography': 'Draft bio',
        },
        event=event,
        user=user,
        not_strict=True,
    )

    assert form.is_valid()
    assert 'fullname' not in form.errors
    assert 'email' not in form.errors
    assert 'avatar' not in form.errors
