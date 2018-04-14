import pytest
from django.core.exceptions import ValidationError

from pretalx.person.models.user import User, nick_validator
from pretalx.submission.models.question import Answer


@pytest.mark.parametrize('nick', (
    'fo',
    'fooo',
    'f'*60,
    '--',
    '__',
    '11',
    'fo-1_0',
))
def test_nick_validator_valid_nicks(nick):
    assert nick_validator(nick) is None


@pytest.mark.parametrize('nick', (
    'f',
    'f*ooo',
    'f'*61,
    '-#-',
    '_ _',
    '@rixx',
))
def test_nick_validator_invalid_nicks(nick):
    with pytest.raises(ValidationError):
        nick_validator(nick)


@pytest.mark.parametrize('email,expected', (
    ('one@two.com', 'ac5be7f974137dc75bacee19b94fe0f8'),
    ('a_very_long.email@orga.org', '79bd022bbbd718d8e30f730169067b2a'),
))
def test_gravatar_parameter(email, expected):
    user = User(email=email)
    assert user.gravatar_parameter == expected


@pytest.mark.django_db
def test_user_deactivate(speaker, personal_answer, impersonal_answer, other_speaker):
    assert Answer.objects.count() == 2
    count = speaker.own_actions().count()
    name = speaker.name
    nick = speaker.nick
    email = speaker.email
    organiser = speaker.submissions.first().event.organiser
    team = organiser.teams.first()
    team.members.add(speaker)
    team.save()
    team_members = team.members.count()
    speaker.deactivate()
    speaker.refresh_from_db()
    assert speaker.own_actions().count() == count
    assert speaker.profiles.first().biography == ''
    assert speaker.name != name
    assert speaker.nick != nick
    assert speaker.nick.startswith('deleted_user')
    assert speaker.email != email
    assert Answer.objects.count() == 1
    assert Answer.objects.first().question.contains_personal_data is False
    assert team.members.count() == team_members - 1
