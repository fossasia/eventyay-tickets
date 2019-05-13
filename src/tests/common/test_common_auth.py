import pytest
from django.test import Client
from rest_framework.authtoken.models import Token


@pytest.mark.flaky(reruns=3)
@pytest.mark.django_db
def test_can_see_schedule_with_bearer_token(event, schedule, slot, orga_user):
    Token.objects.create(user=orga_user)
    client = Client(HTTP_AUTHORIZATION='Token ' + orga_user.auth_token.key)
    event.settings.show_schedule = False
    response = client.get(f'/{event.slug}/schedule.xml')
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()
