import pytest

from pretalx.event.models import Event
from pretalx.mail.models import MailTemplate
from pretalx.person.models import EventPermission, User
from pretalx.submission.models import Question, QuestionVariant, Submission, SubmissionType


@pytest.fixture
def event():
    e = Event.objects.create(name='Fancy testevent', is_public=True, slug='test')
    e.get_cfp()  # created on access
    return e


@pytest.fixture
def question(event):
    return Question.objects.create(event=event, question='How old are you?',
                                   variant=QuestionVariant.NUMBER,
                                   required=False)


@pytest.fixture
def user(event):
    return User.objects.create_user('testuser', 'testpassw0rd')


@pytest.fixture
def orga_user(event):
    user = User.objects.create_user('orgauser', 'orgapassw0rd')
    EventPermission.objects.create(user=user, event=event, is_orga=True)
    return user


@pytest.fixture
def other_orga_user(event):
    user = User.objects.create_user('evilorgauser', 'orgapassw0rd')
    EventPermission.objects.create(user=user, event=event, is_orga=True)
    return user


@pytest.fixture
def orga_client(orga_user, client):
    client.force_login(orga_user)
    return client


@pytest.fixture
def submission_type(event):
    return SubmissionType.objects.create(name='Workshop', event=event)


@pytest.fixture
def speaker():
    return User.objects.create_user('speaker', 'speakerpwd', name='Jane Speaker')


@pytest.fixture
def submission(event, speaker, submission_type):
    return Submission.objects.create(
        title='A Submission', speakers=[speaker], event=event,
        code='BLAKEKS', submission_type=submission_type,
        description='Some talk description', abstract='Fancy abstract',
        notes='I like cookies', content_locale='en'
    )


@pytest.fixture
def invitation(event):
    return EventPermission.objects.create(event=event, is_orga=True, invitation_token='testtoken', invitation_mail='some@test.mail')


@pytest.fixture
def mail_template(event):
    return MailTemplate.objects.create(event=event, subject='Some Mail', text='Whee mail content!')


@pytest.fixture
def mail(mail_template, speaker, event):
    return mail_template.to_mail(speaker, event)
