import pytest


@pytest.mark.django_db
def test_can_login_with_email(speaker, client, event):
    response = client.post(
        event.urls.login,
        data={'login_email': 'jane@speaker.org', 'login_password': 'speakerpwd1!'},
        follow=True,
    )
    assert response.status_code == 200
    assert speaker.get_display_name() in response.content.decode()


@pytest.mark.django_db
def test_cannot_login_with_incorrect_email(client, event, speaker):
    response = client.post(
        event.urls.login,
        data={'login_email': 'jane001@me.space', 'login_password': 'speakerpwd1!'},
        follow=True,
    )
    assert response.status_code == 200
    assert speaker.get_display_name() not in response.content.decode()


@pytest.mark.django_db
def test_cfp_logout(speaker_client, event, speaker):
    response = speaker_client.get(
        event.urls.logout,
        follow=True,
    )
    assert response.status_code == 200
    assert speaker.get_display_name() not in response.content.decode()


@pytest.mark.django_db
def test_can_reset_password_by_email(speaker, client, event):
    response = client.post(
        event.urls.reset,
        data={'login_email': speaker.email, },
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.pw_reset_token
    response = client.post(
        event.urls.reset + f'/{speaker.pw_reset_token}',
        data={'password': 'mynewpassword1!', 'password_repeat': 'mynewpassword1!'},
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert not speaker.pw_reset_token
    response = client.post(
        event.urls.login,
        data={'login_email': speaker.email, 'login_password': 'mynewpassword1!'},
        follow=True,
    )
    assert speaker.get_display_name() in response.content.decode()


@pytest.mark.django_db
def test_cannot_use_incorrect_token(speaker, client, event):
    response = client.post(
        event.urls.reset + f'/abcdefg',
        data={'password': 'mynewpassword1!', 'password_repeat': 'mynewpassword1!'},
        follow=True,
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_cannot_reset_password_with_incorrect_input(speaker, client, event):
    response = client.post(
        event.urls.reset,
        data={'login_email': speaker.email, },
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.pw_reset_token
    response = client.post(
        event.urls.reset + f'/{speaker.pw_reset_token}',
        data={'password': 'mynewpassword1!', 'password_repeat': 'mynewpassword123!'},
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.pw_reset_token
    response = client.post(
        event.urls.login,
        data={'login_email': speaker.email, 'login_password': 'mynewpassword1!'},
        follow=True,
    )
    assert speaker.get_display_name() not in response.content.decode()


@pytest.mark.django_db
def test_cannot_reset_password_to_insecure_password(speaker, client, event):
    response = client.post(
        event.urls.reset,
        data={'login_email': speaker.email, },
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.pw_reset_token
    response = client.post(
        event.urls.reset + f'/{speaker.pw_reset_token}',
        data={'password': 'password', 'password_repeat': 'password'},
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.pw_reset_token
    response = client.post(
        event.urls.login,
        data={'login_email': speaker.email, 'login_password': 'mynewpassword1!'},
        follow=True,
    )
    assert speaker.get_display_name() not in response.content.decode()


@pytest.mark.django_db
def test_cannot_reset_password_without_account(speaker, client, event):
    response = client.post(
        event.urls.reset,
        data={'login_email': 'incorrect' + speaker.email, },
        follow=True,
    )
    assert response.status_code == 200
