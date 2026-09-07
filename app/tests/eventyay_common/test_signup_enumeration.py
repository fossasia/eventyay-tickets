"""Signup must not tell the browser whether an email is already registered."""

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse


User = get_user_model()

SIGNUP_PASSWORD = 'Testpass1!'


def _signup_payload(email: str) -> dict[str, str]:
    return {
        'email': email,
        'password1': SIGNUP_PASSWORD,
        'password2': SIGNUP_PASSWORD,
    }


def _flash_texts(response) -> list[str]:
    return [str(message) for message in get_messages(response.wsgi_request)]


def _post_signup(client, email: str):
    return client.post(
        reverse('account_signup'),
        _signup_payload(email),
        follow=False,
    )


@pytest.mark.django_db
def test_existing_email_signup_uses_the_same_public_path_as_a_new_email(client):
    taken = 'taken@example.com'
    user = User.objects.create_user(email=taken, password=SIGNUP_PASSWORD)
    EmailAddress.objects.create(user=user, email=taken, primary=True, verified=True)

    existing = _post_signup(client, taken)
    new = _post_signup(Client(), 'new-user@example.com')

    assert existing.status_code == new.status_code == 302
    assert existing['Location'] == new['Location']
    assert reverse('account_email_verification_sent') in existing['Location']


@pytest.mark.django_db
def test_signup_flash_does_not_echo_the_submitted_email(client):
    taken = 'admin@example.com'
    user = User.objects.create_user(email=taken, password=SIGNUP_PASSWORD)
    EmailAddress.objects.create(user=user, email=taken, primary=True, verified=True)

    response = _post_signup(client, taken)
    flashes = _flash_texts(response)
    joined = ' '.join(flashes)

    assert flashes
    assert taken not in joined
    assert 'admin@example.com' not in joined

    login = client.get(reverse('auth.login'))
    body = login.content.decode('utf-8')
    assert taken not in body
    assert 'Confirmation e-mail sent to' not in body
    assert 'Confirmation email sent to' not in body
