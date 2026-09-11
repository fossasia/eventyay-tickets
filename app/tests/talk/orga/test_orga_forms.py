import pytest
from django_scopes import scope

from eventyay.base.models import Event
from eventyay.eventyay_common.forms.event import EventCommonSettingsForm
from eventyay.orga.forms import SubmissionForm
from eventyay.orga.forms.event import FeedbackSettingsForm, ReviewScoreCategoryForm


@pytest.mark.django_db
def test_submissionform_content_locale_choices(event):
    event.locale_array = 'en,de'
    event.content_locale_array = 'en,de,fr'
    event.save()
    with scope(event=event):
        submission_form = SubmissionForm(event)
        assert submission_form.fields['content_locale'].choices == [
            ('en', 'English'),
            ('de', 'Deutsch'),
            ('fr', 'Français'),
        ]


def test_event_common_settings_form_has_separate_header_color_controls():
    assert 'header_background_color' in EventCommonSettingsForm.auto_fields
    assert 'header_text_color' in EventCommonSettingsForm.auto_fields
    assert 'navigation_text_color' in EventCommonSettingsForm.auto_fields


def test_event_common_settings_form_includes_date_display_controls():
    assert 'show_date_to' in EventCommonSettingsForm.auto_fields
    assert 'show_times' in EventCommonSettingsForm.auto_fields


@pytest.mark.django_db
def test_review_score_category_form_duplicate_score_validation(event):
    with scope(event=event):
        category = event.score_categories.first()
        scores = list(category.scores.all())

        # Test duplicate values in existing scores
        data_invalid = {
            'name_0': str(category.name),
            'weight': '1',
            f'value_{scores[0].id}': '3',
            f'label_{scores[0].id}': 'Weak',
            f'value_{scores[1].id}': '3',  # Duplicate value 3
            f'label_{scores[1].id}': 'Strong',
            f'value_{scores[2].id}': '5',
            f'label_{scores[2].id}': 'Excellent',
        }
        form_invalid = ReviewScoreCategoryForm(event=event, instance=category, data=data_invalid)
        assert not form_invalid.is_valid()
        assert f'value_{scores[0].id}' not in form_invalid.errors
        assert f'value_{scores[1].id}' in form_invalid.errors
        assert 'Duplicate score values are not allowed' in str(form_invalid.errors[f'value_{scores[1].id}'])

        # Test unique values in existing scores
        data_valid = {
            'name_0': str(category.name),
            'weight': '1',
            f'value_{scores[0].id}': '1',
            f'label_{scores[0].id}': 'Weak',
            f'value_{scores[1].id}': '3',
            f'label_{scores[1].id}': 'Strong',
            f'value_{scores[2].id}': '5',
            f'label_{scores[2].id}': 'Excellent',
        }
        form_valid = ReviewScoreCategoryForm(event=event, instance=category, data=data_valid)
        assert form_valid.is_valid()


def test_feedback_settings_form_defaults():
    """Verify that FeedbackSettingsForm defaults use_feedback to False."""
    event = Event()
    form = FeedbackSettingsForm(obj=event)
    assert form.fields['use_feedback'].initial is False
