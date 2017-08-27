import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_orga_successful_login(client, user):
    user.set_password('testtest')
    user.save()
    response = client.post(reverse('orga:login'), data={'username': user.nick, 'password': 'testtest'}, follow=True)
    assert response.status_code == 200
    assert 'Uh, a new event? Head over here, please!' in response.content.decode()
