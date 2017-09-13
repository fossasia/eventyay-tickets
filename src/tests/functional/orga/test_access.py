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
@pytest.mark.django_db
def test_user_can_access_event_urls(orga_client, url, event):
    response = orga_client.get(reverse(f'orga:{url}', kwargs={'event': event.slug}), follow=True)
    assert response.status_code == 200, response.status_code
    assert event.slug in response.content.decode()


@pytest.mark.parametrize('test_user', ('orga', 'speaker', 'superuser', 'None'))
@pytest.mark.django_db
def test_user_can_see_correct_events(orga_user, orga_client, speaker, event, other_event, test_user):
    if test_user == 'speaker':
        orga_client.force_login(speaker)
    elif test_user == 'None':
        orga_client.logout()
    elif test_user == 'superuser':
        orga_user.is_superuser = True
        orga_user.save()

    response = orga_client.get(reverse('orga:event.dashboard', kwargs={'event': event.slug}), follow=True)

    if test_user == 'speaker':
        assert response.status_code == 403, response.status_code
    elif test_user == 'orga':
        assert event.slug in response.content.decode()
        assert other_event.slug not in response.content.decode()
    elif test_user == 'superuser':
        assert event.slug in response.content.decode(), response.content.decode()
        assert other_event.slug in response.content.decode(), response.content.decode()
    else:
        current_url = response.redirect_chain[-1][0]
        assert 'login' in current_url


@pytest.mark.django_db
def test_dev_settings_warning(orga_client, event, settings):
    settings.DEBUG = True
    response = orga_client.get(reverse('orga:event.dashboard', kwargs={'event': event.slug}), follow=True)
    assert 'running in development mode' in response.content.decode()
