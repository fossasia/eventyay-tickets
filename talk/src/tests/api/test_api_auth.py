import json

import pytest


@pytest.mark.django_db
def test_api_user_endpoint(orga_client, room):
    response = orga_client.get("/api/me", follow=True)
    assert response.status_code == 200
    content = json.loads(response.content.decode())
    assert set(content.keys()) == {"name", "email", "locale", "timezone"}
