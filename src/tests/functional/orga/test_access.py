import pytest
from django.urls import reverse


@pytest.mark.parametrize('url', [
    'login', 'logout', 'dashboard', 'user.view',
])
@pytest.mark.django_db
def test_user_can_access_url(orga_client, url):
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
    assert response.status_code == 200, response.content
    assert event.slug in response.content.decode()
