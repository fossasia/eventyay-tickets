import datetime

import pytest

from pretalx.event.models import Event
from pretalx.person.models import SpeakerProfile, User
from pretalx.schedule.models import Room, TalkSlot
from pretalx.submission.models import Question, Submission


@pytest.fixture
def event():
    return Event.objects.create(name='Event', slug='event', email='orga@org.org',
                                date_from=datetime.date.today(), date_to=datetime.date.today())


@pytest.fixture
def submission(event):
    sub = Submission.objects.create(title='Submission', event=event, submission_type=event.cfp.default_type)
    speaker = User.objects.create_user(name='Speaker', nick='speaker', password='speakerpwd')
    sub.speakers.add(speaker)
    return sub


@pytest.fixture
def room(event):
    return Room.objects.create(name='Roomy', event=event)


@pytest.fixture
def talk_slot(event, submission, room):
    schedule = event.schedules.first()
    return TalkSlot.objects.create(submission=submission, room=room, schedule=schedule, is_visible=True)


@pytest.fixture
def speaker(event):
    user = User.objects.create_user('speaker', 'speakerpwd', name='Jane Speaker', email='jane@speaker.org')
    SpeakerProfile.objects.create(user=user, event=event, biography='Best speaker in the world.')
    return user


@pytest.fixture
def question(submission):
    return Question.objects.create(
        event=submission.event, target='submission', variant='boolean',
        question='Do you agree?',
    )
