import pytest
from django_scopes import scope

from pretalx.orga.forms import SubmissionForm


@pytest.mark.django_db
def test_submissionform_content_locale_choices(event):
    event.locale_array = "en,de"
    event.submission_locale_array = "en,de,fr"
    event.save()
    with scope(event=event):
        submission_form = SubmissionForm(event)
        assert submission_form.fields["content_locale"].choices == [
            ("en", "English"),
            ("de", "German"),
            ("fr", "French"),
        ]
