import pytest
from django.urls import reverse


@pytest.mark.parametrize('test_user', ('orga', 'speaker', 'superuser', 'None'))
@pytest.mark.django_db
def test_dashboard_event_list(orga_user, orga_client, speaker, event, other_event, test_user):
    if test_user == 'speaker':
        orga_client.force_login(speaker)
    elif test_user == 'None':
        orga_client.logout()
    elif test_user == 'superuser':
        orga_user.is_administrator = True
        orga_user.save()

    response = orga_client.get(reverse('orga:event.list'), follow=True)

    if test_user == 'speaker':
        assert response.status_code == 404, response.status_code
    elif test_user == 'orga':
        assert event.slug in response.content.decode()
        assert other_event.slug not in response.content.decode()
    elif test_user == 'superuser':
        assert event.slug in response.content.decode(), response.content.decode()
        assert other_event.slug in response.content.decode(), response.content.decode()
    else:
        current_url = response.redirect_chain[-1][0]
        assert 'login' in current_url


@pytest.mark.parametrize('test_user', ('orga', 'speaker', 'superuser', 'None'))
@pytest.mark.django_db
def test_dashboard_organiser_list(orga_user, orga_client, speaker, event, other_event, test_user):
    if test_user == 'speaker':
        orga_client.force_login(speaker)
    elif test_user == 'None':
        orga_client.logout()
    elif test_user == 'superuser':
        orga_user.is_administrator = True
        orga_user.save()

    response = orga_client.get(reverse('orga:organiser.list'), follow=True)

    if test_user == 'speaker':
        assert response.status_code == 404, response.status_code
    elif test_user == 'orga':
        assert event.organiser.name in response.content.decode()
        assert other_event.organiser.name not in response.content.decode()
    elif test_user == 'superuser':
        assert event.organiser.name in response.content.decode(), response.content.decode()
        assert other_event.organiser.name in response.content.decode(), response.content.decode()
    else:
        current_url = response.redirect_chain[-1][0]
        assert 'login' in current_url
