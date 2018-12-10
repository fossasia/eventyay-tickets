import pytest

from pretalx.api.serializers.event import EventSerializer
from pretalx.api.serializers.question import AnswerSerializer, QuestionSerializer
from pretalx.api.serializers.review import ReviewSerializer
from pretalx.api.serializers.room import RoomOrgaSerializer, RoomSerializer
from pretalx.api.serializers.speaker import (
    SpeakerOrgaSerializer, SpeakerSerializer, SubmitterSerializer,
)
from pretalx.api.serializers.submission import SubmissionSerializer


@pytest.mark.django_db
def test_event_serializer(event):
    data = EventSerializer(event).data
    assert data.keys() == {
        'name',
        'slug',
        'is_public',
        'date_from',
        'date_to',
        'timezone',
        'html_export_url',
    }


@pytest.mark.django_db
def test_question_serializer(answer):
    data = AnswerSerializer(answer).data
    assert set(data.keys()) == {
        'id',
        'question',
        'answer',
        'answer_file',
        'submission',
        'person',
        'options',
    }
    data = QuestionSerializer(answer.question).data
    assert set(data.keys()) == {'id', 'question', 'required', 'target', 'options'}


@pytest.mark.django_db
def test_submitter_serializer(submission):
    user = submission.speakers.first()
    data = SubmitterSerializer(user, context={'event': submission.event}).data
    assert data.keys() == {'name', 'code', 'biography', 'avatar'}
    assert data['name'] == user.name
    assert data['code'] == user.code


@pytest.mark.django_db
def test_submitter_serializer_without_profile(submission):
    user = submission.speakers.first()
    user.profiles.all().delete()
    data = SubmitterSerializer(user, context={'event': submission.event}).data
    assert data.keys() == {'name', 'code', 'biography', 'avatar'}
    assert data['name'] == user.name
    assert data['code'] == user.code
    assert data['biography'] == ''


@pytest.mark.django_db
def test_speaker_serializer(slot):
    user_profile = slot.submission.speakers.first().profiles.first()
    user = user_profile.user
    data = SpeakerSerializer(user_profile).data
    assert data.keys() == {'name', 'code', 'biography', 'submissions', 'avatar'}
    assert data['name'] == user.name
    assert data['code'] == user.code
    assert slot.submission.code in data['submissions']


@pytest.mark.django_db
def test_speaker_orga_serializer(slot):
    user_profile = slot.submission.speakers.first().profiles.first()
    user = user_profile.user
    data = SpeakerOrgaSerializer(user_profile).data
    assert data.keys() == {
        'name',
        'code',
        'biography',
        'submissions',
        'avatar',
        'answers',
        'email',
    }
    assert data['name'] == user.name
    assert data['code'] == user.code
    assert data['email'] == user.email
    assert slot.submission.code in data['submissions']


@pytest.mark.django_db
def test_submission_serializer(submission):
    data = SubmissionSerializer(submission, context={'event': submission.event}).data
    assert set(data.keys()) == {
        'code',
        'speakers',
        'title',
        'submission_type',
        'state',
        'abstract',
        'description',
        'duration',
        'do_not_record',
        'is_featured',
        'content_locale',
        'slot',
        'image',
        'answers',
        'track',
    }
    assert isinstance(data['speakers'], list)
    assert data['speakers'][0] == {
        'name': submission.speakers.first().name,
        'code': submission.speakers.first().code,
        'biography': '',  # Biography can only be derived from request associated event
        'avatar': None,
    }
    assert data['submission_type'] == str(submission.submission_type.name)
    assert data['slot'] is None


@pytest.mark.django_db
def test_submission_slot_serializer(slot):
    data = SubmissionSerializer(
        slot.submission, context={'event': slot.submission.event}
    ).data
    assert set(data.keys()) == {
        'code',
        'speakers',
        'title',
        'submission_type',
        'state',
        'abstract',
        'description',
        'duration',
        'do_not_record',
        'is_featured',
        'content_locale',
        'slot',
        'image',
        'answers',
        'track',
    }
    assert set(data['slot'].keys()) == {'start', 'end', 'room'}
    assert data['slot']['room'] == slot.room.name


@pytest.mark.django_db
def test_review_serializer(review):
    data = ReviewSerializer(review).data
    assert set(data.keys()) == {
        'id',
        'answers',
        'submission',
        'user',
        'text',
        'score',
        'override_vote',
        'created',
        'updated',
    }
    assert data['submission'] == review.submission.code
    assert data['user'] == review.user.name
    assert data['answers'] == []


@pytest.mark.django_db
def test_room_serializer(room):
    data = RoomSerializer(room).data
    assert set(data.keys()) == {'id', 'name', 'description', 'capacity', 'position'}
    assert data['id'] == room.pk


@pytest.mark.django_db
def test_room_orga_serializer(room):
    data = RoomOrgaSerializer(room).data
    assert set(data.keys()) == {
        'id',
        'name',
        'description',
        'capacity',
        'position',
        'speaker_info',
        'availabilities',
    }
    assert data['id'] == room.pk
