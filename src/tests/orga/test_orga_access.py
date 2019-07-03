import pytest
from django.urls import reverse


@pytest.mark.parametrize(
    'url', ['login', 'logout', 'event.list', 'organiser.list', 'user.view']
)
@pytest.mark.parametrize('logged_in', (True, False))
@pytest.mark.django_db
def test_user_can_access_url(orga_client, logged_in, url, template_patch):
    if not logged_in:
        orga_client.logout()
    response = orga_client.get(reverse(f'orga:{url}'), follow=True)
    assert response.status_code == 200, response.content


@pytest.mark.parametrize(
    'url,orga_access,reviewer_access',
    [
        ('event.dashboard', 200, 200),
        ('event.user_list', 200, 200),
        ('cfp.questions.view', 200, 404),
        ('cfp.questions.create', 200, 404),
        ('cfp.questions.remind', 200, 404),
        ('cfp.text.view', 200, 404),
        ('cfp.types.view', 200, 404),
        ('mails.templates.list', 200, 404),
        ('mails.templates.create', 200, 404),
        ('mails.compose', 200, 404),
        ('mails.sent', 200, 404),
        ('mails.outbox.list', 200, 404),
        ('submissions.list', 200, 200),
        ('submissions.statistics', 200, 200),
        ('submissions.create', 200, 404),
        ('submissions.cards', 200, 404),
        ('speakers.list', 200, 200),
        ('speakers.information.list', 200, 404),
        ('speakers.information.create', 200, 404),
        ('reviews.dashboard', 200, 200),
        ('settings.event.view', 200, 404),
        ('settings.mail.view', 200, 404),
        ('settings.plugins.select', 404, 404),
        ('schedule.main', 200, 404),
        ('schedule.export', 200, 404),
        ('schedule.rooms.list', 200, 404),
        ('schedule.rooms.create', 200, 404),
        ('schedule.api.talks', 200, 404),
    ],
)
@pytest.mark.django_db
def test_user_can_access_event_urls(
    orga_user,
    review_user,
    orga_reviewer_user,
    client,
    url,
    orga_access,
    reviewer_access,
    event,
    template_patch,
):
    url = reverse(f'orga:{url}', kwargs={'event': event.slug})
    client.force_login(orga_user)
    orga_response = client.get(url, follow=True)
    client.force_login(review_user)
    review_response = client.get(url, follow=True)
    client.force_login(orga_reviewer_user)
    both_response = client.get(url, follow=True)
    assert orga_response.status_code == orga_access, orga_response.status_code
    assert review_response.status_code == reviewer_access, review_response.status_code
    assert both_response.status_code == min(orga_access, reviewer_access)


@pytest.mark.django_db
def test_speaker_cannot_see_submission_in_orga_area(speaker, submission, client):
    assert speaker in submission.speakers.all()
    client.force_login(speaker)
    response = client.get(submission.orga_urls.base, follow=True)
    assert response.status_code == 404


@pytest.mark.parametrize('test_user', ('orga', 'speaker', 'superuser', 'None'))
@pytest.mark.django_db
def test_user_can_see_correct_events(
    orga_user, orga_client, speaker, event, other_event, test_user
):
    if test_user == 'speaker':
        orga_client.force_login(speaker)
    elif test_user == 'None':
        orga_client.logout()
    elif test_user == 'superuser':
        orga_user.is_administrator = True
        orga_user.save()

    response = orga_client.get(
        reverse('orga:event.dashboard', kwargs={'event': event.slug}), follow=True
    )

    if test_user == 'speaker':
        assert response.status_code == 404, response.status_code
    elif test_user == 'orga':
        assert response.status_code == 200
    elif test_user == 'superuser':
        assert response.status_code == 200
    else:
        current_url = response.redirect_chain[-1][0]
        assert 'login' in current_url


@pytest.mark.django_db
def test_dev_settings_warning(orga_client, event, settings):
    settings.DEBUG = True
    response = orga_client.get(
        reverse('orga:event.dashboard', kwargs={'event': event.slug}), follow=True
    )
    assert 'running in development mode' in response.content.decode()


@pytest.mark.parametrize('test_user', ('orga', 'reviewer'))
@pytest.mark.django_db
def test_user_can_see_correct_urls(orga_user, client, review_user, test_user, event):
    if test_user == 'orga':
        client.force_login(orga_user)
    elif test_user == 'reviewer':
        client.force_login(review_user)

    response = client.get(
        reverse('orga:url_list', kwargs={'event': event.slug}), follow=True
    )
    assert response.status_code == 200
    assert 'Dashboard' in response.content.decode()
