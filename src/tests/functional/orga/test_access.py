import pytest
from django.urls import reverse


@pytest.mark.parametrize('url', [
    'login', 'logout', 'dashboard', 'user.view',
])
@pytest.mark.parametrize('logged_in', (True, False))
@pytest.mark.django_db
def test_user_can_access_url(orga_client, logged_in, url):
    if not logged_in:
        orga_client.logout()
    response = orga_client.get(reverse(f'orga:{url}'), follow=True)
    assert response.status_code == 200, response.content


@pytest.mark.parametrize('url', [
    'event.dashboard', 'cfp.questions.view',
    'cfp.questions.create', 'cfp.text.view', 'cfp.text.edit', 'cfp.types.view',
    'cfp.types.create', 'mails.templates.list', 'mails.templates.create', 'mails.outbox.list',
    'mails.outbox.purge', 'submissions.list', 'speakers.list', 'settings.event.view',
    'settings.event.edit', 'settings.mail.view', 'settings.mail.edit', 'settings.team.view',
])
@pytest.mark.parametrize('test_user', ('orga', 'speaker', 'None'))
@pytest.mark.django_db
def test_user_can_access_event_urls(orga_client, speaker, test_user, url, event):
    if test_user == 'None':
        orga_client.logout()
    elif test_user == 'speaker':
        orga_client.force_login(speaker)
    response = orga_client.get(reverse(f'orga:{url}', kwargs={'event': event.slug}), follow=True)

    if test_user != 'speaker':
        assert response.status_code == 200, response.status_code
    else:
        assert response.status_code == 403, response.status_code

    assert (event.slug in response.content.decode()) == (test_user == 'orga')

    if test_user == 'None':
        current_url = response.redirect_chain[-1][0]
        assert 'login' in current_url


@pytest.mark.parametrize('url,obj', [
    ('cfp.question.edit', 'question'),
    ('cfp.question.delete', 'question'),
    ('cfp.type.delete', 'submission_type'),
    ('cfp.type.edit', 'submission_type'),
    ('mails.templates.edit', 'mail_template'),
    ('mails.templates.delete', 'mail_template'),
    ('mails.outbox.mail.view', 'mail'),
    ('mails.outbox.mail.edit', 'mail'),
    ('mails.outbox.mail.send', 'mail'),
    ('mails.outbox.mail.delete', 'mail'),
    ('submissions.content.view', 'submission'),
    ('submissions.content.edit', 'submission'),
    ('submissions.accept', 'submission'),
    ('submissions.reject', 'submission'),
    ('submissions.questions.edit', 'submission'),
    ('submissions.speakers.view', 'submission'),
    ('speakers.view', 'speaker'),
    ('speakers.edit', 'speaker'),
    ('settings.team.delete', 'other_orga_user'),
    ('settings.team.retract', 'invitation'),
])
@pytest.mark.django_db
def test_user_can_access_specific_urls(orga_client, url, obj, event, question, submission_type, mail_template, mail, submission, speaker, other_orga_user, invitation):
    obj = locals().get(obj)
    response = orga_client.get(reverse(f'orga:{url}', kwargs={'event': event.slug, 'pk': obj.pk}), follow=True)
    assert response.status_code == 200, response.content
    assert event.slug in response.content.decode()
