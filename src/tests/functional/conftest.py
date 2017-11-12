import datetime

import pytest
import pytz
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now

from pretalx.event.models import Event
from pretalx.mail.models import MailTemplate
from pretalx.person.models import EventPermission, SpeakerProfile, User
from pretalx.schedule.models import Availability, Room, TalkSlot
from pretalx.submission.models import (
    Answer, AnswerOption, Feedback, Question, QuestionVariant,
    Resource, Review, Submission, SubmissionType,
)


@pytest.fixture
def template_patch(monkeypatch):
    # Patch out template rendering for performance improvements
    monkeypatch.setattr("django.template.backends.django.Template.render", lambda *args, **kwargs: "mocked template")


@pytest.fixture
def event():
    today = datetime.date.today()
    return Event.objects.create(
        name='Fancy testevent', is_public=True, slug='test', email='orga@orga.org',
        date_from=today, date_to=today + datetime.timedelta(days=3)
    )


@pytest.fixture
def other_event():
    return Event.objects.create(name='Boring testevent', is_public=True, slug='test2', email='orga2@orga.org',
                                date_from=datetime.date.today(), date_to=datetime.date.today())


@pytest.fixture
def multilingual_event():
    today = datetime.date.today()
    return Event.objects.create(
        name='Fancy testevent', is_public=True, slug='test2', email='orga@orga.org',
        date_from=today, date_to=today + datetime.timedelta(days=3), locale_array='en,de',
    )


@pytest.fixture
def resource(submission):
    f = SimpleUploadedFile('testresource.txt', b'a resource')
    return Resource.objects.create(submission=submission, resource=f, description='Test resource')


@pytest.fixture
def other_resource(submission):
    f = SimpleUploadedFile('testresource2.txt', b'another resource')
    return Resource.objects.create(submission=submission, resource=f, description='Test resource 2')


@pytest.fixture
def question(event):
    return Question.objects.create(
        event=event, question='How much do you like green, on a scale from 1-10?', variant=QuestionVariant.NUMBER,
        target='submission', required=False,
    )


@pytest.fixture
def inactive_question(event):
    return Question.objects.create(
        event=event, question='So, on a scale from 1–100, how much do you like red?', variant=QuestionVariant.NUMBER,
        target='submission', required=False, active=False,
    )


@pytest.fixture
def answer(event, submission, question):
    return Answer.objects.create(answer='11', submission=submission, question=question)


@pytest.fixture
def speaker_question(event):
    return Question.objects.create(
        event=event, question='What is your favourite color?', variant=QuestionVariant.STRING,
        target='speaker', required=False,
    )


@pytest.fixture
def speaker_boolean_question(event):
    return Question.objects.create(
        event=event, question='Do you like green?', variant=QuestionVariant.BOOLEAN,
        target='speaker', required=False,
    )


@pytest.fixture
def speaker_file_question(event):
    return Question.objects.create(
        event=event, question='Please submit your CV.', variant=QuestionVariant.FILE,
        target='speaker', required=False,
    )


@pytest.fixture
def choice_question(event):
    question = Question.objects.create(
        event=event, question='How much do you like green?', variant=QuestionVariant.CHOICES,
        target='speaker', required=False,
    )
    for answer in ['very', 'incredibly', 'omggreen']:
        AnswerOption.objects.create(question=question, answer=answer)
    return question


@pytest.fixture
def multiple_choice_question(event):
    question = Question.objects.create(
        event=event, question='Which colors other than green do you like?', variant=QuestionVariant.MULTIPLE,
        target='speaker', required=False,
    )
    for answer in ['yellow', 'blue', 'black']:
        AnswerOption.objects.create(question=question, answer=answer)
    return question


@pytest.fixture
def speaker_text_question(event):
    return Question.objects.create(
        event=event, question='Please elaborat on your like/dislike of green.',
        variant=QuestionVariant.TEXT, target='speaker', required=False,
    )


@pytest.fixture
def user():
    return User.objects.create_user('testuser', 'testpassw0rd!')


@pytest.fixture
def superuser():
    return User.objects.create_superuser('testuser', 'testpassw0rd!')


@pytest.fixture
def orga_user(event):
    user = User.objects.create_user('orgauser', 'orgapassw0rd', email='orgauser@orga.org')
    EventPermission.objects.create(user=user, event=event, is_orga=True, is_reviewer=False)
    return user


@pytest.fixture
def other_orga_user(event):
    user = User.objects.create_user('evilorgauser', 'orgapassw0rd', email='evilorgauser@orga.org')
    EventPermission.objects.create(user=user, event=event, is_orga=True, is_reviewer=False)
    return user


@pytest.fixture
def review_user(event):
    user = User.objects.create_user('reviewuser', 'reviewpassw0rd', email='reviewuser@orga.org')
    EventPermission.objects.create(user=user, event=event, is_orga=False, is_reviewer=True)
    return user


@pytest.fixture
def other_review_user(event):
    user = User.objects.create_user('evilreviewuser', 'reviewpassw0rd', email='evilreviewuser@orga.org')
    EventPermission.objects.create(user=user, event=event, is_orga=False, is_reviewer=True)
    return user


@pytest.fixture
def orga_reviewer_user(event):
    user = User.objects.create_user('multitalentuser', 'orgapassw0rd', email='multiuser@orga.org')
    EventPermission.objects.create(user=user, event=event, is_orga=True, is_reviewer=True)
    return user


@pytest.fixture
def orga_client(orga_user, client):
    client.force_login(orga_user)
    return client


@pytest.fixture
def other_orga_client(other_orga_user, client):
    client.force_login(other_orga_user)
    return client


@pytest.fixture
def review_client(review_user, client):
    client.force_login(review_user)
    return client


@pytest.fixture
def other_review_client(other_review_user, client):
    client.force_login(other_review_user)
    return client


@pytest.fixture
def superuser_client(superuser, client):
    client.force_login(superuser)
    return client


@pytest.fixture
def submission_type(event):
    return SubmissionType.objects.create(name='Workshop', event=event)


@pytest.fixture
def default_submission_type(event):
    return event.cfp.default_type


@pytest.fixture
def speaker(event):
    user = User.objects.create_user('speaker', 'speakerpwd1!', name='Jane Speaker', email='jane@speaker.org')
    SpeakerProfile.objects.create(user=user, event=event, biography='Best speaker in the world.')
    return user


@pytest.fixture
def speaker_client(client, speaker):
    client.force_login(speaker)
    return client


@pytest.fixture
def other_speaker(event):
    user = User.objects.create_user('speaker2', 'speakerpwd1!', name='Krümelmonster')
    SpeakerProfile.objects.create(user=user, event=event, biography='COOKIIIIES!!')
    return user


@pytest.fixture
def submission_data(event, submission_type):
    return {
        'title': 'Lametta im Wandel der Zeiten',
        # 'code': 'LAMETTA',
        'submission_type': submission_type,
        'description': 'Früher war es nämlich mehr. Und wir mussten es bügeln.',
        'abstract': 'Ich habe Quellen!',
        'notes': 'Und mein Enkel braucht auch noch ein Geschenk.',
        'content_locale': 'en',
        'event': event,
    }


@pytest.fixture
def submission(submission_data, speaker):
    sub = Submission.objects.create(**submission_data)
    sub.save()
    sub.speakers.add(speaker)
    return sub


@pytest.fixture
def other_submission(event, other_speaker):
    sub = Submission.objects.create(
        title='Albrecht Dürer. Sein Leben, seine Zeit', event=event,
        code='BLAKOKS', submission_type=event.cfp.default_type,
        description='1 guter Talk', abstract='Verstehste?',
        notes='I like cookies A LOT', content_locale='en'
    )
    sub.save()
    sub.speakers.add(other_speaker)
    return sub


@pytest.fixture
def accepted_submission(speaker, submission_data):
    sub = Submission.objects.create(**submission_data)
    sub.save()
    sub.speakers.add(speaker)
    sub.accept()
    return sub


@pytest.fixture
def other_accepted_submission(other_submission):
    other_submission.accept()
    return other_submission


@pytest.fixture
def rejected_submission(submission_data, speaker):
    sub = Submission.objects.create(**submission_data)
    sub.save()
    sub.speakers.add(speaker)
    sub.reject()
    return sub


@pytest.fixture
def confirmed_submission(submission_data, speaker):
    sub = Submission.objects.create(**submission_data)
    sub.save()
    sub.speakers.add(speaker)
    sub.accept()
    sub.confirm()
    return sub


@pytest.fixture
def other_confirmed_submission(other_accepted_submission):
    other_accepted_submission.confirm()
    return other_accepted_submission


@pytest.fixture
def canceled_submission(submission_data, speaker):  # TODO: implement Submission.canceled
    sub = Submission.objects.create(**submission_data)
    sub.save()
    sub.speakers.add(speaker)
    sub.state = 'canceled'
    sub.save()
    return sub


@pytest.fixture
def withdrawn_submission(submission_data, speaker):  # TODO: implement Submission.withdraw()
    sub = Submission.objects.create(**submission_data)
    sub.save()
    sub.speakers.add(speaker)
    sub.state = 'withdrawn'
    sub.save()
    return sub


@pytest.fixture
def invitation(event):
    return EventPermission.objects.create(event=event, is_orga=True, invitation_token='testtoken', invitation_email='some@test.mail')


@pytest.fixture
def mail_template(event):
    return MailTemplate.objects.create(event=event, subject='Some Mail', text='Whee mail content!', reply_to='orga@orga.org')


@pytest.fixture(scope='function')
def mail(mail_template, speaker, event):
    return mail_template.to_mail(speaker, event)


@pytest.fixture(scope='function')
def other_mail(mail_template, event, speaker):
    return mail_template.to_mail(speaker, event)


@pytest.fixture
def sent_mail(mail_template, speaker, event):
    mail = mail_template.to_mail(speaker, event)
    mail.send()
    return mail


@pytest.fixture
def room(event):
    return Room.objects.create(event=event, name='Testroom', description='A fancy room', position=2, capacity=50)


@pytest.fixture
def room_availability(event, room, availability):
    availability.room = room
    availability.save()
    return availability


@pytest.fixture
def availability(event):
    return Availability(
        event=event,
        start=datetime.datetime.combine(event.date_from, datetime.time.min, tzinfo=pytz.utc),
        end=datetime.datetime.combine(event.date_to, datetime.time.max, tzinfo=pytz.utc),
    )


@pytest.fixture
def schedule(event):
    event.release_schedule('Best Version')
    return event.current_schedule


@pytest.fixture
def slot(confirmed_submission, room, schedule):
    slot = schedule.talks.filter(submission=confirmed_submission)
    slot.update(start=now(), end=now() + datetime.timedelta(minutes=30), submission=confirmed_submission, room=room, schedule=schedule, is_visible=True)
    slot = slot.first()
    return slot


@pytest.fixture
def past_slot(submission_data, room, schedule, speaker):
    sub = Submission.objects.create(**submission_data)
    sub.speakers.add(speaker)
    sub.save()
    sub.accept()
    sub.confirm()
    return TalkSlot.objects.create(start=now() - datetime.timedelta(minutes=60), end=now() - datetime.timedelta(minutes=30), submission=sub, room=room, schedule=schedule, is_visible=True)


@pytest.fixture
def feedback(past_slot):
    return Feedback.objects.create(talk=past_slot.submission, review='I liked it!')


@pytest.fixture
def other_slot(other_confirmed_submission, room, schedule):
    return TalkSlot.objects.create(start=now(), end=now() + datetime.timedelta(minutes=30), submission=other_confirmed_submission, room=room, schedule=schedule, is_visible=True)


@pytest.fixture
def schedule_schema():
    from lxml import etree
    with open('tests/functional/fixtures/schedule.xsd', 'r') as xsd:
        source = xsd.read()
    schema = etree.XML(source)
    return etree.XMLSchema(schema)


@pytest.fixture
def review(submission, review_user):
    return Review.objects.create(score=1, submission=submission, user=review_user, text='Looks great!')
