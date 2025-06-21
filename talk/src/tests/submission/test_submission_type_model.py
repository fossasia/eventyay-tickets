import pytest
from django_scopes import scope

from pretalx.submission.models import SubmissionType


@pytest.mark.parametrize(
    "duration,string",
    (
        (30, "30 minutes"),
        (60, "60 minutes"),
        (90, "90 minutes"),
        (120, "2 hours"),
        (150, "2.5 hours"),
        (60 * 24, "24 hours"),
        (60 * 48, "2 days"),
    ),
)
def test_submission_type_string(duration, string):
    assert (
        str(SubmissionType(default_duration=duration, name="Test"))
        == f"Test ({string})"
    )


@pytest.mark.django_db
def test_update_times(event, accepted_submission, confirmed_submission):
    with scope(event=event):
        submission_type = accepted_submission.submission_type
        assert submission_type == confirmed_submission.submission_type
        confirmed_submission.duration = 5
        confirmed_submission.save()
        slot = accepted_submission.slots.filter(schedule__version__isnull=True).first()
        assert slot.duration == submission_type.default_duration
        submission_type.default_duration += 30
        submission_type.save()
        submission_type.update_duration()
        slot.refresh_from_db()
        assert slot.duration == submission_type.default_duration
        assert (
            confirmed_submission.slots.filter(schedule__version__isnull=True)
            .first()
            .duration
            != submission_type.default_duration
        )
