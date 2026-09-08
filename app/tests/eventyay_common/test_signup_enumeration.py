"""Signup must not tell the browser whether an email is already registered."""

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse


User = get_user_model()

SIGNUP_PASSWORD = 'Testpass1!'
GENERIC_FLASH = 'We have sent a confirmation email. Check your inbox to continue.'
VERIFY_PAGE_COPY = 'We have sent an email to you for verification.'


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
    unused = 'new-user@example.com'
    user = User.objects.create_user(email=taken, password=SIGNUP_PASSWORD)
    EmailAddress.objects.create(user=user, email=taken, primary=True, verified=True)

    unused_client = Client()
    existing = _post_signup(client, taken)
    unused_resp = _post_signup(unused_client, unused)
    existing_verify = client.get(existing['Location']).content.decode('utf-8')
    unused_verify = unused_client.get(unused_resp['Location']).content.decode('utf-8')
    existing_login = client.get(reverse('auth.login')).content.decode('utf-8')
    unused_login = unused_client.get(reverse('auth.login')).content.decode('utf-8')
    existing_flash = ' '.join(_flash_texts(existing))
    unused_flash = ' '.join(_flash_texts(unused_resp))

    assert existing_flash
    assert unused_flash == existing_flash
    assert GENERIC_FLASH in existing_flash
    assert VERIFY_PAGE_COPY in existing_verify
    assert VERIFY_PAGE_COPY in unused_verify
    assert GENERIC_FLASH in existing_login
    assert GENERIC_FLASH in unused_login
    for text in (
        existing_flash,
        unused_flash,
        existing_verify,
        unused_verify,
        existing_login,
        unused_login,
    ):
        assert taken not in text
        assert unused not in text
        assert 'Confirmation e-mail sent to' not in text
        assert 'Confirmation email sent to' not in text
