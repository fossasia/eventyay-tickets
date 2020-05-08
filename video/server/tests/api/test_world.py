import pytest
from tests.api.utils import get_token_header


@pytest.mark.django_db
def test_world_config(client, world):
    r = client.get("/api/v1/worlds/sample/", HTTP_AUTHORIZATION=get_token_header(world))
    assert r.status_code == 200
    assert r.data == {
        "id": "sample",
        "title": "Unsere tolle Online-Konferenz",
        "about": "# Unsere tolle Online-Konferenz\n\nHallo!\nDas ist ein Markdowntext!",
        "config": world.config,
        "permission_config": world.permission_config,
        "domain": None,
    }


@pytest.mark.django_db
def test_world_config_protect_secrets(client, world):
    world.permission_config["world.secrets"] = ["foobartrait"]
    world.save()
    r = client.get("/api/v1/worlds/sample/", HTTP_AUTHORIZATION=get_token_header(world))
    assert r.status_code == 403
    r = client.get(
        "/api/v1/worlds/sample/",
        HTTP_AUTHORIZATION=get_token_header(world, ["api", "foobartrait", "admin"]),
    )
    assert r.status_code == 200


@pytest.mark.django_db
def test_world_update(client, world):
    world.permission_config["world.update"] = ["foobartrait"]
    world.save()

    r = client.patch(
        "/api/v1/worlds/sample/",
        {"title": "Democon"},
        HTTP_AUTHORIZATION=get_token_header(world),
    )
    assert r.status_code == 403

    r = client.patch(
        "/api/v1/worlds/sample/",
        {"title": "Democon"},
        HTTP_AUTHORIZATION=get_token_header(world, ["foobartrait", "admin", "api"]),
    )
    assert r.status_code == 200
    world.refresh_from_db()
    assert world.title == "Democon"


@pytest.mark.django_db
def test_world_no_delete(client, world):
    r = client.delete(
        "/api/v1/worlds/sample/",
        {"title": "Democon"},
        HTTP_AUTHORIZATION=get_token_header(world),
    )
    assert r.status_code == 403
