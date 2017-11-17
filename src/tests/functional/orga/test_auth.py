import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_orga_successful_login(client, user, template_patch):
    user.set_password('testtest')
    user.save()
    response = client.post(reverse('orga:login'), data={'username': user.nick, 'password': 'testtest'}, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_redirect_login(client, orga_user, event):
    queryparams = 'foo=bar&something=else'
    request_url = event.orga_urls.base + '/?' + queryparams
    response = client.get(request_url, follow=True)
    assert response.status_code == 200
    assert response.redirect_chain[-1] == (f'/orga/login/?next={event.orga_urls.base}/&{queryparams}', 302)

    response = client.post(response.redirect_chain[-1][0], data={'username': orga_user.nick, 'password': 'orgapassw0rd'}, follow=True)
    assert response.status_code == 200
    assert event.name in response.content.decode()
    assert response.redirect_chain[-1][0] == request_url


@pytest.mark.django_db
def test_orga_accept_invitation_once(client, event, invitation):
    assert invitation.user is None
    response = client.post(
        reverse('orga:invitation.view', kwargs={'code': invitation.invitation_token}),
        {
            'register_username': 'newuser',
            'register_email': invitation.invitation_email,
            'register_password': 'f00baar!',
            'register_password_repeat': 'f00baar!',
        },
        follow=True,
    )
    assert response.status_code == 200
    invitation.refresh_from_db()
    assert invitation.user.nick == 'newuser'
    response = client.post(
        reverse('orga:invitation.view', kwargs={'code': invitation.invitation_token}),
        {
            'register_username': 'evilnewuser',
            'register_email': invitation.invitation_email + '.evil',
            'register_password': 'f00baar!',
            'register_password_repeat': 'f00baar!',
        },
        follow=True,
    )
    assert response.status_code == 404
    invitation.refresh_from_db()
    assert invitation.user.nick == 'newuser'
