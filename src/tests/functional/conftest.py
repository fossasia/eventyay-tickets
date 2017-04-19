import pytest

from pretalx.event.models import Event
from pretalx.person.models import User
from pretalx.submission.models import Question, QuestionVariant


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
