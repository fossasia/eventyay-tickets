import pytest
from django.core.exceptions import ValidationError

from eventyay.base.models import Event, Room, User
from eventyay.base.services.event import create_room
from eventyay.core.permissions import Permission
from eventyay.features.live.modules.bbb import BBBModule
from eventyay.features.live.modules.jitsi import (
    JitsiModule,
    build_jitsi_config_overwrite,
)
from eventyay.features.live.modules.januscall import JanusCallModule


@pytest.mark.django_db
def test_event_video_defaults_serialization():
    from django.utils.timezone import now
    from django_scopes import scopes_disabled
    from eventyay.base.models import Organizer
    from eventyay.base.services.event import _config_serializer, EventConfigSerializer

    with scopes_disabled():
        organizer = Organizer.objects.create(name="Test Org", slug="test-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Test Event",
            slug="test-event",
            date_from=now(),
            config={
                "bbb_defaults": {
                    "record": True,
                    "waiting_room": True,
                    "bbb_disable_cam": True,
                },
                "jitsi_defaults": {
                    "start_with_audio_muted": True,
                    "waiting_room": True,
                    "record": True,
                    "disable_cam": True,
                },
                "janus_defaults": {
                    "waiting_room": True,
                    "disable_cam": True,
                },
                "zoom_defaults": {
                    "disable_chat": True,
                    "enable_platform_chat": True,
                    "enable_platform_qa": True,
                    "enable_platform_polls": False,
                },
            },
        )
        s = _config_serializer(event)
        data = s.data
        assert data["bbb_defaults"]["record"] is True
        assert data["bbb_defaults"]["waiting_room"] is True
        assert data["bbb_defaults"]["bbb_disable_cam"] is True
        assert data["jitsi_defaults"]["start_with_audio_muted"] is True
        assert data["jitsi_defaults"]["waiting_room"] is True
        assert data["janus_defaults"]["waiting_room"] is True
        assert data["janus_defaults"]["disable_cam"] is True
        assert data["zoom_defaults"]["disable_chat"] is True
        assert data["zoom_defaults"]["enable_platform_qa"] is True

        # Test serializer partial update
        patch_data = {
            "jitsi_defaults": {
                "start_with_audio_muted": False,
                "waiting_room": False,
            },
            "janus_defaults": {
                "waiting_room": True,
                "disable_cam": False,
            },
            "zoom_defaults": {
                "disable_chat": False,
                "enable_platform_qa": False,
            },
        }
        s2 = _config_serializer(event, data=patch_data, partial=True)
        assert s2.is_valid(), s2.errors
        assert s2.validated_data["jitsi_defaults"]["start_with_audio_muted"] is False
        assert s2.validated_data["janus_defaults"]["disable_cam"] is False
        assert s2.validated_data["zoom_defaults"]["disable_chat"] is False




from types import SimpleNamespace
from asgiref.sync import async_to_sync
from eventyay.base.services import event as event_service


class ChannelLayer:
    async def group_send(self, *args, **kwargs):
        pass


def test_create_room_applies_event_video_defaults(monkeypatch):
    created = {}

    async def fake_create_room(data, with_channel=False, **kwargs):
        created["data"] = data
        return SimpleNamespace(id="room-id", module_config=data.get("modules")), None

    async def _allow_permission(**kwargs):
        return True

    async def _allow_server_backed(*args, **kwargs):
        return True

    monkeypatch.setattr(event_service, "_create_room", fake_create_room)
    monkeypatch.setattr(event_service, "get_channel_layer", lambda: ChannelLayer())
    monkeypatch.setattr(
        event_service,
        "user_can_create_server_backed_room_during_development",
        _allow_server_backed,
    )

    event = SimpleNamespace(
        id="test-event-1",
        config={
            "bbb_defaults": {
                "record": False,
                "waiting_room": True,
                "bbb_disable_cam": False,
                "bbb_disable_chat": False,
            },
            "jitsi_defaults": {
                "start_with_audio_muted": True,
                "start_with_video_muted": False,
                "record": False,
                "livestreaming": False,
                "waiting_room": True,
                "disable_cam": False,
                "disable_chat": False,
                "require_display_name": False,
            },
            "janus_defaults": {
                "start_with_audio_muted": False,
                "start_with_video_muted": False,
                "waiting_room": True,
                "disable_cam": True,
                "disable_chat": False,
            },
            "zoom_defaults": {
                "disable_chat": True,
            },
        },
        has_permission_async=_allow_permission,
    )
    user = SimpleNamespace(id="user-1")

    # 1. Jitsi room creation with platform defaults merged with room-specific overrides
    jitsi_data = {
        "name": "Jitsi Test Room",
        "modules": [
            {
                "type": "call.jitsi",
                "config": {
                    "start_with_video_muted": True,
                    "record": True,
                },
            }
        ],
    }
    async_to_sync(event_service.create_room)(event, jitsi_data, user)
    jitsi_module = [m for m in created["data"]["module_config"] if m["type"] == "call.jitsi"][0]
    # Inherited from platform settings
    assert jitsi_module["config"]["waiting_room"] is True
    assert jitsi_module["config"]["start_with_audio_muted"] is True
    # Provided explicitly in room setup
    assert jitsi_module["config"]["start_with_video_muted"] is True
    assert jitsi_module["config"]["record"] is True

    # 2. BBB room creation with platform defaults
    bbb_data = {
        "name": "BBB Test Room",
        "modules": [
            {
                "type": "call.bigbluebutton",
                "config": {
                    "record": True,
                },
            }
        ],
    }
    async_to_sync(event_service.create_room)(event, bbb_data, user)
    bbb_module = [m for m in created["data"]["module_config"] if m["type"] == "call.bigbluebutton"][0]
    assert bbb_module["config"]["waiting_room"] is True
    assert bbb_module["config"]["record"] is True

    # 3. Janus room creation with platform defaults
    janus_data = {
        "name": "Janus Test Room",
        "modules": [
            {
                "type": "call.janus",
                "config": {
                    "waiting_room": True,
                },
            }
        ],
    }
    async_to_sync(event_service.create_room)(event, janus_data, user)
    janus_module = [m for m in created["data"]["module_config"] if m["type"] == "call.janus"][0]
    assert janus_module["config"]["waiting_room"] is True
    assert janus_module["config"]["disable_cam"] is True

    # 4. Zoom room creation with platform defaults and chat/question/poll modules
    zoom_data = {
        "name": "Zoom Test Room",
        "modules": [
            {
                "type": "call.zoom",
                "config": {
                    "meeting_number": "1234567890",
                    "password": "secretpassword",
                },
            },
            {
                "type": "chat.native",
                "config": {"volatile": True},
            },
            {
                "type": "question",
                "config": {"active": True},
            },
            {
                "type": "poll",
                "config": {"active": True},
            },
        ],
    }
    async_to_sync(event_service.create_room)(event, zoom_data, user)
    zoom_module = [m for m in created["data"]["module_config"] if m["type"] == "call.zoom"][0]
    assert zoom_module["config"]["meeting_number"] == "1234567890"
    assert zoom_module["config"]["password"] == "secretpassword"
    assert zoom_module["config"]["disable_chat"] is True
    module_types = [m["type"] for m in created["data"]["module_config"]]
    assert "chat.native" in module_types
    assert "question" in module_types
    assert "poll" in module_types


def test_jitsi_config_overwrite_enforces_room_options():
    # Non-moderator in room with waiting_room, disable_cam, and disable_chat
    module_config = {
        "waiting_room": True,
        "disable_cam": True,
        "disable_chat": True,
        "require_display_name": True,
        "record": False,
        "livestreaming": False,
    }
    cfg_user = build_jitsi_config_overwrite(
        module_config,
        is_moderator=False,
        room_display_name="Workshop 1",
        has_jwt=True,
    )
    assert cfg_user["enableLobby"] is True
    assert cfg_user["lobby"]["enable"] is True
    assert cfg_user["disableChat"] is True
    assert cfg_user["startWithVideoMuted"] is True
    assert "camera" not in cfg_user["toolbarButtons"]
    assert "chat" not in cfg_user["toolbarButtons"]
    assert cfg_user["requireDisplayName"] is True
    assert cfg_user["prejoinPageEnabled"] is True

    # Moderator in same room
    cfg_mod = build_jitsi_config_overwrite(
        module_config,
        is_moderator=True,
        room_display_name="Workshop 1",
        has_jwt=True,
    )
    assert cfg_mod["enableLobby"] is True
    assert "disableChat" not in cfg_mod or cfg_mod["disableChat"] is False
    assert "camera" in cfg_mod["toolbarButtons"]
    assert "recording" not in cfg_mod["toolbarButtons"]
    assert "livestreaming" not in cfg_mod["toolbarButtons"]


def test_janus_waiting_room_enabled_flag():
    assert JanusCallModule._is_waiting_room_enabled({"waiting_room": True}) is True
    assert JanusCallModule._is_waiting_room_enabled({"waiting_room_enabled": True}) is True
    assert JanusCallModule._is_waiting_room_enabled({"waiting_room": False}) is False
    assert JanusCallModule._is_waiting_room_enabled({}) is False


def test_server_backed_rooms_strip_platform_interaction_modules():
    from eventyay.base.services.room import _sanitize_server_backed_interaction_modules

    # Server-backed room with chat.native, question, and poll
    module_config = [
        {"type": "call.bigbluebutton", "config": {}},
        {"type": "chat.native", "config": {}},
        {"type": "question", "config": {}},
        {"type": "poll", "config": {}},
    ]
    _sanitize_server_backed_interaction_modules(module_config)
    types = [m["type"] for m in module_config]
    assert types == ["call.bigbluebutton"]

    # Jitsi room
    jitsi_config = [
        {"type": "call.jitsi", "config": {}},
        {"type": "chat.native", "config": {}},
    ]
    _sanitize_server_backed_interaction_modules(jitsi_config)
    assert [m["type"] for m in jitsi_config] == ["call.jitsi"]

    # Zoom room
    zoom_config = [
        {"type": "call.zoom", "config": {}},
        {"type": "chat.native", "config": {}},
        {"type": "poll", "config": {}},
    ]
    _sanitize_server_backed_interaction_modules(zoom_config)
    assert [m["type"] for m in zoom_config] == ["call.zoom"]

    # Janus room (WebRTC SFU, not embedded suite) keeps interaction modules
    janus_config = [
        {"type": "call.janus", "config": {}},
        {"type": "chat.native", "config": {}},
        {"type": "question", "config": {}},
        {"type": "poll", "config": {}},
    ]
    _sanitize_server_backed_interaction_modules(janus_config)
    assert [m["type"] for m in janus_config] == ["call.janus", "chat.native", "question", "poll"]

    # Stage room (livestream) keeps chat.native and questions
    stage_config = [
        {"type": "livestream.native", "config": {}},
        {"type": "chat.native", "config": {}},
        {"type": "question", "config": {}},
    ]
    _sanitize_server_backed_interaction_modules(stage_config)
    assert len(stage_config) == 3


@pytest.mark.django_db
def test_all_video_servers_toggle_active_status(client):
    from django.contrib.auth import get_user_model
    from eventyay.base.models.auth import StaffSession
    from eventyay.base.models import BBBServer, JitsiServer, JanusServer, TurnServer

    User = get_user_model()
    admin = User.objects.create(
        email="admin_video_toggle@test.local",
        is_active=True,
        is_staff=True,
        is_administrator=True,
    )
    admin.set_password("adminpass")
    admin.save()

    client.force_login(admin)
    session = client.session
    session.save()
    StaffSession.objects.create(user=admin, session_key=session.session_key)

    bbb = BBBServer.objects.create(url="https://bbb-toggle.test/bigbluebutton/api", secret="secret", active=True)
    jitsi = JitsiServer.objects.create(url="https://jitsi-toggle.test", active=False)
    janus = JanusServer.objects.create(url="https://janus-toggle.test", active=True)
    turn = TurnServer.objects.create(hostname="turn-toggle.test", active=False)

    # 1. Video settings view renders toggle inputs without active/inactive badges
    res = client.get("/admin/video/settings/")
    assert res.status_code == 200
    content = res.content.decode()
    assert "data-video-server-toggle" in content
    assert "video-server-toggle" in content
    assert "video-status-badge" not in content

    # 2. Toggle active state for all four server types
    for server_type, server, expected_initial in [
        ("bbb", bbb, True),
        ("jitsi", jitsi, False),
        ("janus", janus, True),
        ("turn", turn, False),
    ]:
        toggle_url = f"/admin/video/servers/{server_type}/{server.pk}/toggle-active/"
        target_state = not expected_initial

        # Toggle to new state
        resp = client.post(toggle_url, data={"active": target_state}, content_type="application/json")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["ok"] is True
        assert payload["active"] is target_state

        server.refresh_from_db()
        assert server.active is target_state

        # Toggle back
        resp2 = client.post(toggle_url, data={"active": expected_initial}, content_type="application/json")
        assert resp2.status_code == 200
        assert resp2.json()["active"] is expected_initial

        server.refresh_from_db()
        assert server.active is expected_initial


