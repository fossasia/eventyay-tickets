import pytest
from django.conf import settings

from tests.utils import get_token_header


@pytest.mark.django_db
def test_world_config(client, world):
    r = client.get("/api/v1/worlds/sample/", HTTP_AUTHORIZATION=get_token_header(world))
    assert r.status_code == 200
    assert r.data == {
        "id": "sample",
        "title": "Unsere tolle Online-Konferenz",
        "config": world.config,
        "roles": world.roles,
        "trait_grants": world.trait_grants,
        "domain": "localhost",
    }


@pytest.mark.django_db
def test_world_config_protect_secrets(client, world):
    world.trait_grants["apiuser"] = ["foobartrait"]
    world.save()
    r = client.get("/api/v1/worlds/sample/", HTTP_AUTHORIZATION=get_token_header(world))
    assert r.status_code == 403
    r = client.get(
        "/api/v1/worlds/sample/",
        HTTP_AUTHORIZATION=get_token_header(world, ["api", "foobartrait", "admin"]),
    )
    assert r.status_code == 200
    world.roles["apiuser"] = ["world:api"]
    world.save()
    r = client.get(
        "/api/v1/worlds/sample/",
        HTTP_AUTHORIZATION=get_token_header(world, ["api", "admin", "foobartrait"]),
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_world_update(client, world):
    world.trait_grants["apiuser"] = ["foobartrait"]
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


@pytest.mark.django_db
@pytest.mark.skipif(
    settings.REDIS_USE_PUBSUB, reason="asyncio weirdness makes this fail"
)
@pytest.mark.parametrize(
    "data", ({}, {"event": "foo"}, {"domain": "https://pretalx.dev"})
)
def test_schedule_update_domain_and_event_required(client, world, data):
    assert not world.config["pretalx"].get("connected")
    r = client.post(
        "/api/v1/worlds/sample/schedule_update",
        data,
        format="json",
        HTTP_AUTHORIZATION=get_token_header(world, ["admin", "api"]),
    )
    assert r.status_code == 401
    assert r.content.decode() == '"Missing fields in request."'
    world.refresh_from_db()
    assert not world.config["pretalx"].get("connected")


@pytest.mark.django_db
@pytest.mark.skipif(
    settings.REDIS_USE_PUBSUB, reason="asyncio weirdness makes this fail"
)
def test_schedule_update_wrong_event(client, world):
    assert not world.config["pretalx"].get("connected")
    r = client.post(
        "/api/v1/worlds/sample/schedule_update",
        {"domain": "https://pretalx.dev", "event": "foo"},
        format="json",
        HTTP_AUTHORIZATION=get_token_header(world, ["admin", "api"]),
    )
    assert r.status_code == 401
    assert r.content.decode() == '"Incorrect domain or event data"'
    world.refresh_from_db()
    assert not world.config["pretalx"].get("connected")


@pytest.mark.django_db
@pytest.mark.skipif(
    settings.REDIS_USE_PUBSUB, reason="asyncio weirdness makes this fail"
)
def test_schedule_update(client, world):
    assert not world.config["pretalx"].get("connected")
    world.config["pretalx"]["domain"] = "https://pretalx.dev"
    world.config["pretalx"]["event"] = "demofon"
    world.save()

    r = client.post(
        "/api/v1/worlds/sample/schedule_update",
        {
            "domain": "https://pretalx.dev",
            "event": "demofon",
        },
        format="json",
        HTTP_AUTHORIZATION=get_token_header(world, ["foobartrait", "admin", "api"]),
    )
    assert r.status_code == 200
    world.refresh_from_db()
    assert world.config["pretalx"]["domain"] == "https://pretalx.dev"
    assert world.config["pretalx"]["event"] == "demofon"
    assert world.config["pretalx"]["connected"] is True
