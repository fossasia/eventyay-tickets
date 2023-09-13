import json
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils.timezone import now

from venueless.core.models.room import AnonymousInvite


@pytest.mark.django_db
def test_detect_world(client, world):
    r = client.get("/foo", HTTP_HOST="foobar.com")
    assert r.status_code == 404

    world.domain = "foobar.com"
    world.save()

    r = client.get("/foo", HTTP_HOST="foobar.com")
    assert r.status_code == 200


@pytest.mark.django_db
def test_manifest(client, world):
    world.domain = "foobar.com"
    world.save()
    r = client.get("/manifest.json", HTTP_HOST="foobar.com")
    assert r.status_code == 200
    assert json.loads(r.content)["name"] == world.title


@pytest.mark.django_db
def test_known_anonymous_invite_on_main_domain(client, world, stream_room):
    world.domain = "foobar.com"
    world.save()
    ai = AnonymousInvite.objects.create(
        world=world,
        room=stream_room,
        expires=now() + timedelta(days=1),
    )
    r = client.get("/" + ai.short_token, HTTP_HOST="localhost")
    assert r.status_code == 302
    assert (
        r["Location"]
        == f"http://foobar.com/standalone/{stream_room.id}/anonymous#invite={ai.short_token}"
    )


@pytest.mark.django_db
def test_unknown_anonymous_invite_on_main_domain(client, world, stream_room):
    world.domain = "foobar.com"
    world.save()
    r = client.get("/aaaaaa", HTTP_HOST="localhost")
    assert r.status_code == 404


@pytest.mark.django_db
def test_known_anonymous_invite_on_world_domain(client, world, stream_room):
    world.domain = "foobar.com"
    world.save()
    ai = AnonymousInvite.objects.create(
        world=world,
        room=stream_room,
        expires=now() + timedelta(days=1),
    )
    r = client.get("/" + ai.short_token, HTTP_HOST="foobar.com")
    assert r.status_code == 302
    assert (
        r["Location"]
        == f"http://foobar.com/standalone/{stream_room.id}/anonymous#invite={ai.short_token}"
    )


@pytest.mark.django_db
def test_unknown_anonymous_invite_on_world_domain(client, world, stream_room):
    world.domain = "foobar.com"
    world.save()
    r = client.get("/aaaaaa", HTTP_HOST="foobar.com")
    # We do not show a 404 since theoretically this could be a vlaid path recognized by
    # the frontend router.
    assert r.status_code == 200


@pytest.mark.django_db
@override_settings(SHORT_URL="https://vnls.io")
def test_known_anonymous_invite_on_short_domain(client, world, stream_room):
    world.domain = "foobar.com"
    world.save()
    ai = AnonymousInvite.objects.create(
        world=world,
        room=stream_room,
        expires=now() + timedelta(days=1),
    )
    r = client.get("/" + ai.short_token, HTTP_HOST="foobar.com")
    assert r.status_code == 200  # no 404, could be a valid frontend router URL
    r = client.get("/" + ai.short_token, HTTP_HOST="vnls.io")
    assert r.status_code == 302
    assert (
        r["Location"]
        == f"http://foobar.com/standalone/{stream_room.id}/anonymous#invite={ai.short_token}"
    )


@pytest.mark.django_db
@override_settings(SHORT_URL="https://vnls.io")
def test_unknown_anonymous_invite_on_short_domain(client, world, stream_room):
    world.domain = "foobar.com"
    world.save()
    r = client.get("/aaaaaa", HTTP_HOST="vnls.io")
    assert r.status_code == 404
    assert b"Invalid link" in r.content


@pytest.mark.django_db
@override_settings(SHORT_URL="https://vnls.io")
def test_index_on_short_domain(client, world, stream_room):
    r = client.get("/", HTTP_HOST="vnls.io")
    assert r.status_code == 200
    assert b"URL='http" in r.content
