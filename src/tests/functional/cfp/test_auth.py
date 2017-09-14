import pytest


@pytest.mark.django_db
def test_can_login_with_username(speaker, client, event):
    response = client.post(
        event.urls.login,
        data={'login_username': 'speaker', 'login_password': 'speakerpwd'},
        follow=True,
    )
    assert response.status_code == 200
    assert 'My submissions' in response.content.decode()


@pytest.mark.django_db
def test_can_login_with_email(speaker, client, event):
    response = client.post(
        event.urls.login,
        data={'login_username': 'jane@speaker.org', 'login_password': 'speakerpwd'},
        follow=True,
    )
    assert response.status_code == 200
    assert 'My submissions' in response.content.decode()


@pytest.mark.django_db
def test_cannot_login_with_incorrect_username(client, event):
    response = client.post(
        event.urls.login,
        data={'login_username': 'jane001', 'login_password': 'speakerpwd'},
        follow=True,
    )
    assert response.status_code == 200
    assert 'My submissions' not in response.content.decode()


@pytest.mark.django_db
def test_cannot_login_with_incorrect_email(client, event):
    response = client.post(
        event.urls.login,
        data={'login_username': 'jane001@me.space', 'login_password': 'speakerpwd'},
        follow=True,
    )
    assert response.status_code == 200
    assert 'My submissions' not in response.content.decode()
