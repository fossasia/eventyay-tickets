import pytest

from pretalx.api.serializers.event import EventSerializer
from pretalx.api.serializers.speaker import SubmitterSerializer
from pretalx.api.serializers.submission import SubmissionSerializer


@pytest.mark.django_db
def test_event_serializer(event):
    data = EventSerializer(event).data
    assert data.keys() == {
        'name', 'slug', 'subtitle', 'is_public', 'date_from', 'date_to',
        'timezone', 'html_export_url',
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
    assert set(data.keys()) == {
        'code', 'speakers', 'title', 'submission_type', 'state', 'abstract',
        'description', 'duration', 'do_not_record', 'content_locale', 'slot',
    }
    assert isinstance(data['speakers'], list)
    assert data['speakers'][0] == {
        'name': submission.speakers.first().name,
        'code': submission.speakers.first().code,
    }
    assert data['submission_type'] == str(submission.submission_type.name)
    assert data['slot'] is None


@pytest.mark.django_db
def test_submission_slot_serializer(slot):
    data = SubmissionSerializer(slot.submission, context={'event': slot.submission.event}).data
    assert set(data.keys()) == {
        'code', 'speakers', 'title', 'submission_type', 'state', 'abstract',
        'description', 'duration', 'do_not_record', 'content_locale', 'slot',
    }
    assert set(data['slot'].keys()) == {'start', 'end', 'room'}
    assert data['slot']['room'] == slot.room.name
