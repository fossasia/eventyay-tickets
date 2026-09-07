import asyncio
import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch
import pytest
from django.test import Client
from django.utils import timezone
from django_scopes import scope, scopes_disabled
import jwt

from eventyay.base.models import Event, LoungeMeshAccessToken, LoungeMeshServer, Organizer, Room, User
from eventyay.base.services.loungemesh import (
    apply_loungemesh_embed_headers,
    clean_expired_loungemesh_tokens,
    get_loungemesh_server,
    issue_jitsi_jwt,
    issue_join_url,
    issue_opaque_token,
    loungemesh_is_available,
    loungemesh_permissions_policy,
    verify_loungemesh_token,
)
from eventyay.control.forms.server_management import LoungeMeshServerForm
from eventyay.core.permissions import Permission
from eventyay.features.live.modules.loungemesh import LoungeMeshModule


@pytest.fixture
def test_setup():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="LoungeMesh Org", slug="lm-org")
        event = Event.objects.create(
            organizer=organizer,
            name="LoungeMesh Event",
            slug="lm-event",
            date_from=timezone.now(),
            date_to=timezone.now() + timedelta(days=2),
            live=True,
        )
        user = User.objects.create(
            email="attendee@example.com",
            fullname="Alice Attendee",
        )
        moderator_user = User.objects.create(
            email="mod@example.com",
            fullname="Bob Moderator",
        )
        server = LoungeMeshServer.objects.create(
            url="http://localhost:8780",
            api_secret="test_lm_secret",
            jitsi_app_id="eventyay",
            jitsi_app_secret="test_jitsi_jwt_secret",
            active=True,
            cost=0,
        )
        with scope(event=event):
            room = Room.objects.create(
                event=event,
                name="Spatial Lounge",
                module_config=[
                    {
                        "type": "call.loungemesh",
                        "config": {
                            "prefer_server": "http://localhost:8780",
                            "enable_notes": True,
                            "enable_whiteboard": True,
                            "enable_spatial_chat": True,
                        },
                    }
                ],
            )

    return {
        "organizer": organizer,
        "event": event,
        "user": user,
        "moderator_user": moderator_user,
        "server": server,
        "room": room,
    }


@pytest.mark.django_db
def test_loungemesh_server_model_and_form(test_setup):
    server = test_setup["server"]
    assert str(server) == "http://localhost:8780"
    assert server.active is True
    assert server.cost == 0

    # Test Form validation and normalization
    form_data = {
        "url": "http://localhost:8780/",
        "api_secret": "my_secret",
        "jitsi_app_id": "eventyay",
        "jitsi_app_secret": "my_jitsi_secret",
        "cost": 5,
        "active": True,
    }
    form = LoungeMeshServerForm(data=form_data)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.url == "http://localhost:8780"  # trailing slash stripped


@pytest.mark.django_db
def test_get_loungemesh_server_selection(test_setup):
    event = test_setup["event"]
    server = test_setup["server"]

    # When active server is present
    selected = get_loungemesh_server(event=event)
    assert selected == server
    assert loungemesh_is_available(event=event) is True

    # Preferred server selection
    preferred = get_loungemesh_server(event=event, prefer_server="http://localhost:8780")
    assert preferred == server

    # If all servers are inactive
    server.active = False
    server.save()
    assert get_loungemesh_server(event=event) is None
    assert loungemesh_is_available(event=event) is False


@pytest.mark.django_db
def test_token_issue_and_verify(test_setup):
    event = test_setup["event"]
    user = test_setup["user"]
    room = test_setup["room"]

    # Issue token for attendee (moderator=False)
    token_obj = issue_opaque_token(event=event, room=room, user=user, moderator=False, expires_in_seconds=900)
    assert len(token_obj.token) > 20

    record = verify_loungemesh_token(token_obj.token)
    assert record is not None
    assert record.user == user
    assert record.room == room
    assert record.event == event
    assert record.moderator is False
    assert record.is_valid is True

    # Issue token for moderator (moderator=True)
    mod_user = test_setup["moderator_user"]
    mod_token_obj = issue_opaque_token(event=event, room=room, user=mod_user, moderator=True, expires_in_seconds=900)
    mod_record = verify_loungemesh_token(mod_token_obj.token)
    assert mod_record is not None
    assert mod_record.moderator is True

    # Verify invalid token
    assert verify_loungemesh_token("invalid_token_string") is None

    # Test expired token
    with scope(event=event):
        record.expires = timezone.now() - timedelta(minutes=5)
        record.save()
    assert verify_loungemesh_token(token_obj.token) is None


@pytest.mark.django_db
def test_clean_expired_tokens(test_setup):
    event = test_setup["event"]
    user = test_setup["user"]
    room = test_setup["room"]

    token_obj = issue_opaque_token(event=event, room=room, user=user, expires_in_seconds=900)
    with scope(event=event):
        LoungeMeshAccessToken.objects.filter(token=token_obj.token).update(expires=timezone.now() - timedelta(minutes=10))
        cleaned = clean_expired_loungemesh_tokens()
        assert cleaned >= 1
        assert LoungeMeshAccessToken.objects.filter(token=token_obj.token).count() == 0


@pytest.mark.django_db
def test_issue_jitsi_jwt(test_setup):
    server = test_setup["server"]
    event = test_setup["event"]
    user = test_setup["user"]
    room = test_setup["room"]

    token_str = issue_jitsi_jwt(
        display_name=user.fullname,
        jitsi_room=f"lms-{event.slug}-{room.id}",
        moderator=False,
        app_id=server.jitsi_app_id,
        app_secret=server.jitsi_app_secret,
    )
    assert token_str is not None

    payload = jwt.decode(token_str, server.jitsi_app_secret, algorithms=["HS256"], audience="eventyay")
    assert payload["iss"] == "eventyay"
    assert payload["aud"] == "eventyay"
    assert payload["room"] == f"lms-{event.slug}-{room.id}"
    assert payload["context"]["user"]["name"] == user.fullname
    assert payload["context"]["user"]["moderator"] is False

    # For moderator
    mod_token = issue_jitsi_jwt(
        display_name=test_setup["moderator_user"].fullname,
        jitsi_room=f"lms-{event.slug}-{room.id}",
        moderator=True,
        app_id=server.jitsi_app_id,
        app_secret=server.jitsi_app_secret,
    )
    mod_payload = jwt.decode(mod_token, server.jitsi_app_secret, algorithms=["HS256"], audience="eventyay")
    assert mod_payload["context"]["user"]["moderator"] is True


@pytest.mark.django_db
def test_issue_join_url(test_setup):
    server = test_setup["server"]
    event = test_setup["event"]
    user = test_setup["user"]
    room = test_setup["room"]

    join_url = issue_join_url(
        event=event,
        room=room,
        user=user,
        moderator=False,
        server=server,
    )
    assert join_url is not None
    assert join_url.startswith("http://localhost:8780/join/")
    assert "?token=" in join_url
    assert f"/join/lms-{event.slug}-{room.id}" in join_url


@pytest.mark.django_db
def test_loungemesh_token_exchange_view(test_setup):
    client = Client()
    event = test_setup["event"]
    user = test_setup["user"]
    room = test_setup["room"]

    # 1. Missing token
    resp = client.post("/api/v1/loungemesh/token/", data=json.dumps({}), content_type="application/json")
    assert resp.status_code == 400

    # 2. Invalid token
    resp = client.post("/api/v1/loungemesh/token/", data=json.dumps({"token": "fake"}), content_type="application/json")
    assert resp.status_code == 403

    # 3. Valid token but missing or invalid API secret -> 401 Unauthorized
    token_obj = issue_opaque_token(event=event, room=room, user=user, moderator=False, expires_in_seconds=1800)
    resp = client.post("/api/v1/loungemesh/token/", data=json.dumps({"token": token_obj.token}), content_type="application/json")
    assert resp.status_code == 401
    assert resp.json()["error"] == "unauthorized"

    resp = client.post(
        "/api/v1/loungemesh/token/",
        data=json.dumps({"token": token_obj.token}),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer wrong_secret",
    )
    assert resp.status_code == 401

    # 4. Valid attendee token with Authorization Bearer header -> 200 OK
    resp = client.post(
        "/api/v1/loungemesh/token/",
        data=json.dumps({"token": token_obj.token}),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer test_lm_secret",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "granted"
    assert data["display_name"] == user.fullname
    assert data["moderator"] is False
    assert data["jwt"] is not None
    assert data["features"]["notes"] is True
    assert data["features"]["whiteboard"] is True
    assert data["features"]["spatial_chat"] is True

    # 5. Valid moderator token with X-LoungeMesh-Secret header -> 200 OK
    mod_user = test_setup["moderator_user"]
    mod_token_obj = issue_opaque_token(event=event, room=room, user=mod_user, moderator=True, expires_in_seconds=1800)
    resp = client.post(
        "/api/v1/loungemesh/token/",
        data=json.dumps({"token": mod_token_obj.token}),
        content_type="application/json",
        HTTP_X_LOUNGEMESH_SECRET="test_lm_secret",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["moderator"] is True


@pytest.mark.django_db
def test_loungemesh_token_refresh_view(test_setup):
    client = Client()
    event = test_setup["event"]
    user = test_setup["user"]
    room = test_setup["room"]

    token_obj = issue_opaque_token(event=event, room=room, user=user, moderator=False, expires_in_seconds=1800)
    # Without secret -> 401
    resp = client.post("/api/v1/loungemesh/token/refresh/", data=json.dumps({"token": token_obj.token}), content_type="application/json")
    assert resp.status_code == 401

    # With Bearer secret -> 200
    resp = client.post(
        "/api/v1/loungemesh/token/refresh/",
        data=json.dumps({"token": token_obj.token}),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer test_lm_secret",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "refreshed"
    assert data["jwt"] is not None
    assert data["expires_at"] is not None


class DummyConsumer:
    def __init__(self, user, world, permissions=None, room_cache=None):
        self.user = user
        self.world = world
        self.event = world
        self.permissions = set(permissions or [])
        self.room_cache = room_cache or {}
        self.sent_data = None

    async def has_permission_async(self, perm):
        pval = perm.value if hasattr(perm, "value") else str(perm)
        return pval in self.permissions or perm in self.permissions

    def has_permission(self, perm):
        pval = perm.value if hasattr(perm, "value") else str(perm)
        return pval in self.permissions or perm in self.permissions

    async def send_success(self, data):
        self.sent_data = data
        return data


@pytest.mark.django_db
def test_loungemesh_websocket_module(test_setup):
    event = test_setup["event"]
    user = test_setup["user"]
    mod_user = test_setup["moderator_user"]
    room = test_setup["room"]

    room_cache = {str(room.id): room}

    async def fake_get_join_url(is_moderator):
        return f"http://localhost:8780/room?token=dummy_token&mod={is_moderator}"

    # Regular attendee consumer (no moderate permission)
    attendee_consumer = DummyConsumer(
        user=user,
        world=event,
        permissions=[Permission.ROOM_LOUNGEMESH_JOIN.value],
        room_cache=room_cache,
    )

    # Moderator consumer (with ROOM_LOUNGEMESH_MODERATE)
    mod_consumer = DummyConsumer(
        user=mod_user,
        world=event,
        permissions=[Permission.ROOM_LOUNGEMESH_JOIN.value, Permission.ROOM_LOUNGEMESH_MODERATE.value],
        room_cache=room_cache,
    )

    async def mock_event_has_permission(*, user, permission, room=None):
        perms = attendee_consumer.permissions if user == attendee_consumer.user else mod_consumer.permissions
        perms_list = permission if isinstance(permission, (list, set, tuple)) else [permission]
        return any(
            (p.value if hasattr(p, "value") else str(p)) in perms or p in perms
            for p in perms_list
        )

    module = LoungeMeshModule(attendee_consumer)

    with (
        patch.object(room, "refresh_from_db_if_outdated", new_callable=AsyncMock),
        patch.object(event, "has_permission_async", side_effect=mock_event_has_permission),
        patch.object(module, "_get_join_url", side_effect=fake_get_join_url),
    ):
        asyncio.run(module.room_url({"room": str(room.id)}))
    res = attendee_consumer.sent_data
    assert res is not None
    assert "url" in res
    assert res["moderator"] is False
    assert "token=" in res["url"]

    # Moderator consumer (with ROOM_LOUNGEMESH_MODERATE)
    mod_module = LoungeMeshModule(mod_consumer)
    with (
        patch.object(room, "refresh_from_db_if_outdated", new_callable=AsyncMock),
        patch.object(event, "has_permission_async", side_effect=mock_event_has_permission),
        patch.object(mod_module, "_get_join_url", side_effect=fake_get_join_url),
    ):
        asyncio.run(mod_module.room_url({"room": str(room.id)}))
    mod_res = mod_consumer.sent_data
    assert mod_res is not None
    assert "url" in mod_res
    assert mod_res["moderator"] is True


@pytest.mark.django_db
def test_embed_headers_and_permissions_policy(test_setup):
    policy = loungemesh_permissions_policy(["http://localhost:8780"])
    assert "camera=(self" in policy
    assert '"http://localhost:8780"' in policy
    assert "microphone=(self" in policy
    assert "display-capture=(self" in policy

    class MockResponse(dict):
        pass

    response = MockResponse()
    apply_loungemesh_embed_headers(response, ["http://localhost:8780"])
    assert "Permissions-Policy" in response
