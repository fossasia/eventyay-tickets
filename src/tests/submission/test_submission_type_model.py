import pytest

from pretalx.submission.models import SubmissionType


@pytest.mark.parametrize('duration,string', (
    (30, '30 minutes'),
    (60, '60 minutes'),
    (90, '90 minutes'),
    (120, '2 hours'),
    (150, '2.5 hours'),
    (60*24, '24 hours'),
    (60*48, '2 days'),
))
def test_submission_type_string(duration, string):
    assert str(SubmissionType(default_duration=duration, name='Test')) == f'Test ({string})'
