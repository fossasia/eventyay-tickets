import pytest
from django.test import Client
from rest_framework.authtoken.models import Token


@pytest.mark.flaky(reruns=3)
@pytest.mark.django_db
def test_can_see_schedule_with_bearer_token(event, schedule, slot, orga_user):
    Token.objects.create(user=orga_user)
    client = Client(headers={"authorization": "Token " + orga_user.auth_token.key})
    event.feature_flags["show_schedule"] = False
    event.save()
    response = client.get(f"/{event.slug}/schedule.xml")
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.flaky(reruns=3)
@pytest.mark.django_db
def test_cannot_see_schedule_with_wrong_bearer_token(event, schedule, slot, orga_user):
    Token.objects.create(user=orga_user)
    client = Client(
        headers={"authorization": "Token " + orga_user.auth_token.key + "xxx"}
    )
    event.feature_flags["show_schedule"] = False
    event.save()
    response = client.get(f"/{event.slug}/schedule.xml")
    assert response.status_code == 404
    assert slot.submission.title not in response.content.decode()
