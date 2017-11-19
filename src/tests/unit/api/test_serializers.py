import pytest

from pretalx.api.serializers.event import EventSerializer
from pretalx.api.serializers.speaker import SubmitterSerializer
from pretalx.api.serializers.submission import SubmissionSerializer


@pytest.mark.django_db
def test_event_serializer(event):
    data = EventSerializer(event).data
    assert data.keys() == {
        'name', 'slug', 'subtitle', 'is_public', 'date_from', 'date_to',
        'timezone',
    }


@pytest.mark.django_db
def test_submitter_serializer(submission):
    user = submission.speakers.first()
    data = SubmitterSerializer(user, context={'event': submission.event}).data
    assert data.keys() == {'name', 'code'}
    assert data['name'] == user.name
    assert data['code'] == user.code


@pytest.mark.django_db
def test_submission_serializer(submission):
    data = SubmissionSerializer(submission, context={'event': submission.event}).data
    assert data.keys() == {
        'code', 'speakers', 'title', 'submission_type', 'state', 'abstract',
        'description', 'duration', 'do_not_record', 'content_locale',
    }
    assert isinstance(data['speakers'], list)
    assert data['speakers'][0] == {
        'name': submission.speakers.first().name,
        'code': submission.speakers.first().code,
    }
