import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Room
from eventyay.base.models.auth import StaffSession
from eventyay.base.services.event import create_room, get_event_config_for_user, get_rooms
from eventyay.base.settings import (
    GlobalSettingsObject,
    SUPPORTED_VIDEO_PROVIDERS,
    get_video_provider_visibility,
    is_room_visible_for_attendee,
    is_video_provider_enabled_for_attendee,
    is_video_provider_enabled_for_organizer,
)


@pytest.fixture
def admin_user():
    User = get_user_model()
    admin = User.objects.create(
        email="admin_video_vis@test.local",
        is_active=True,
        is_staff=True,
        is_administrator=True,
        traits=["admin"],
    )
    admin.set_password("adminpass")
    admin.save()
    return admin


@pytest.fixture
def attendee_user():
    User = get_user_model()
    attendee = User.objects.create(
        email="attendee_video_vis@test.local",
        is_active=True,
        is_staff=False,
        is_administrator=False,
        traits=["attendee"],
    )
    attendee.set_password("attendeepass")
    attendee.save()
    return attendee


@pytest.fixture
def sample_event():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Vis Org", slug="vis-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Vis Event",
            slug="vis-event",
            date_from=now(),
            trait_grants={
                "viewer": ["attendee"],
                "attendee": ["attendee"],
            },
        )
        return event



@pytest.mark.django_db
def test_video_provider_visibility_defaults_and_helpers():
    gs = GlobalSettingsObject()
    # Reset all to default True
    for p in SUPPORTED_VIDEO_PROVIDERS:
        gs.settings.set(f"video_provider_{p}_organizer", True)
        gs.settings.set(f"video_provider_{p}_attendee", True)

    vis = get_video_provider_visibility()
    for p in ("bbb", "jitsi", "janus", "loungemesh", "zoom"):
        assert p in vis
        assert vis[p]["organizer"] is True
        assert vis[p]["attendee"] is True
        assert is_video_provider_enabled_for_organizer(p) is True
        assert is_video_provider_enabled_for_attendee(p) is True

    # Change Jitsi organizer to False
    gs.settings.set("video_provider_jitsi_organizer", False)
    assert is_video_provider_enabled_for_organizer("jitsi") is False
    assert is_video_provider_enabled_for_attendee("jitsi") is True

    # Change LoungeMesh attendee to False
    gs.settings.set("video_provider_loungemesh_attendee", False)
    assert is_video_provider_enabled_for_organizer("loungemesh") is True
    assert is_video_provider_enabled_for_attendee("loungemesh") is False

    # Cleanup
    gs.settings.set("video_provider_jitsi_organizer", True)
    gs.settings.set("video_provider_loungemesh_attendee", True)


@pytest.mark.django_db
def test_admin_video_settings_view_and_ajax_toggle(client, admin_user):
    client.force_login(admin_user)
    session = client.session
    session.save()
    StaffSession.objects.create(user=admin_user, session_key=session.session_key)

    # 1. GET /admin/video/settings/ renders General tab as active
    res = client.get("/admin/video/settings/")
    assert res.status_code == 200
    content = res.content.decode()
    assert "General" in content
    assert "video-provider-visibility-toggle" in content
    assert "Video Server Visibility & Access Control" in content

    # 2. Toggle via AJAX endpoint
    toggle_url = "/admin/video/settings/toggle-visibility/"
    resp = client.post(
        toggle_url,
        data={"provider": "jitsi", "role": "organizer", "enabled": False},
        content_type="application/json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["enabled"] is False
    assert is_video_provider_enabled_for_organizer("jitsi") is False

    # Toggle back
    resp = client.post(
        toggle_url,
        data={"provider": "jitsi", "role": "organizer", "enabled": True},
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    assert is_video_provider_enabled_for_organizer("jitsi") is True

    # 3. Form submit (POST /admin/video/settings/)
    post_data = {
        "video_provider_bbb_organizer": "on",
        "video_provider_bbb_attendee": "on",
        "video_provider_jitsi_organizer": "on",
        # disable Jitsi for attendees: omit video_provider_jitsi_attendee
        "video_provider_janus_organizer": "on",
        "video_provider_janus_attendee": "on",
        "video_provider_loungemesh_organizer": "on",
        "video_provider_loungemesh_attendee": "on",
        "video_provider_zoom_organizer": "on",
        "video_provider_zoom_attendee": "on",
    }
    resp = client.post("/admin/video/settings/", data=post_data)
    assert resp.status_code == 302
    assert is_video_provider_enabled_for_attendee("jitsi") is False
    assert is_video_provider_enabled_for_organizer("jitsi") is True

    # Cleanup
    gs = GlobalSettingsObject()
    gs.settings.set("video_provider_jitsi_attendee", True)


@pytest.mark.django_db
def test_create_room_blocked_when_provider_disabled_for_organizers(sample_event, admin_user):
    gs = GlobalSettingsObject()
    gs.settings.set("video_provider_jitsi_organizer", False)

    try:
        with pytest.raises(ValidationError) as exc:
            async_to_sync(create_room)(
                sample_event,
                {
                    "name": "Forbidden Jitsi Room",
                    "modules": [{"type": "call.jitsi", "config": {}}],
                },
                creator=admin_user,
            )
        assert "disabled for room creation" in str(exc.value)
    finally:
        gs.settings.set("video_provider_jitsi_organizer", True)


@pytest.mark.django_db
def test_get_rooms_filters_rooms_for_attendees(sample_event, attendee_user, admin_user):
    from django_scopes import scope

    with scope(event=sample_event):
        jitsi_room = Room.objects.create(
            event=sample_event,
            name="Jitsi Room",
            module_config=[{"type": "call.jitsi", "config": {}}],
            trait_grants={"viewer": []},
        )
        bbb_room = Room.objects.create(
            event=sample_event,
            name="BBB Room",
            module_config=[{"type": "call.bigbluebutton", "config": {}}],
            trait_grants={"viewer": []},
        )

    gs = GlobalSettingsObject()
    gs.settings.set("video_provider_jitsi_attendee", False)
    gs.settings.set("video_provider_bbb_attendee", True)

    try:
        # Attendee should NOT see the Jitsi room
        attendee_rooms = get_rooms(sample_event, attendee_user)
        attendee_room_ids = [r.id for r in attendee_rooms]
        assert bbb_room.id in attendee_room_ids
        assert jitsi_room.id not in attendee_room_ids

        # Admin / organizer SHOULD see all rooms
        admin_rooms = get_rooms(sample_event, admin_user)
        admin_room_ids = [r.id for r in admin_rooms]
        assert bbb_room.id in admin_room_ids
        assert jitsi_room.id in admin_room_ids

        # World config exposes video_providers
        cfg = get_event_config_for_user(sample_event, attendee_user)
        assert "video_providers" in cfg["world"]
        assert cfg["world"]["video_providers"]["jitsi"]["attendee"] is False
    finally:
        gs.settings.set("video_provider_jitsi_attendee", True)


@pytest.mark.django_db
def test_get_room_config_marks_disabled_for_inactive_provider(sample_event):
    from django_scopes import scope
    from eventyay.base.services.event import get_room_config

    with scope(event=sample_event):
        jitsi_room = Room.objects.create(
            event=sample_event,
            name="Jitsi Room Disabled Test",
            module_config=[{"type": "call.jitsi", "config": {}}],
            trait_grants={"viewer": []},
        )

    gs = GlobalSettingsObject()
    gs.settings.set("video_provider_jitsi_attendee", False)

    try:
        cfg = get_room_config(jitsi_room, permissions=set())
        assert cfg["is_disabled"] is True
        assert "no longer available" in cfg["disabled_reason"]
    finally:
        gs.settings.set("video_provider_jitsi_attendee", True)


@pytest.mark.asyncio
async def test_get_room_config_for_user_prevents_direct_access_for_attendees(mocker):
    from unittest.mock import MagicMock
    from eventyay.base.services.event import get_room_config_for_user

    mock_event = MagicMock()
    mock_room = MagicMock()
    mock_room.event = mock_event
    mock_room.module_config = [{"type": "call.jitsi", "config": {}}]

    attendee = MagicMock()
    admin = MagicMock()

    mock_event.get_all_permissions.side_effect = lambda u: (
        {mock_room: set(), mock_event: set()}
        if u == attendee
        else {mock_room: {"room:update"}, mock_event: {"event:update"}}
    )

    mocker.patch("eventyay.base.services.event.get_room", return_value=mock_room)
    mocker.patch("eventyay.base.services.event.is_room_visible_for_attendee", return_value=False)
    mocker.patch(
        "eventyay.base.services.event.get_room_config",
        return_value={
            "is_disabled": True,
            "disabled_reason": "This feature is no longer available. Please contact system administrator.",
        },
    )

    # Attendee receives None (blocked direct access)
    attendee_cfg = await get_room_config_for_user("room-123", "event-123", attendee)
    assert attendee_cfg is None

    # Admin receives config marked as disabled with reason
    admin_cfg = await get_room_config_for_user("room-123", "event-123", admin)
    assert admin_cfg is not None
    assert admin_cfg["is_disabled"] is True
    assert "no longer available" in admin_cfg["disabled_reason"]


@pytest.mark.django_db
def test_video_server_routing_multi_event_and_multi_organizer(sample_event):
    from eventyay.base.models import Event, JitsiServer, Organizer
    from eventyay.base.services.jitsi import _choose_any_available_server
    from eventyay.base.services.video_server_routing import is_server_available_for_event

    with scopes_disabled():
        org2 = Organizer.objects.create(name="Other Org", slug="other-org")
        event2 = Event.objects.create(organizer=org2, name="Event 2", slug="event-2", date_from=now())
        event3 = Event.objects.create(organizer=sample_event.organizer, name="Event 3", slug="event-3", date_from=now())

        JitsiServer.objects.all().delete()

        # 1. Global server (no events, no organizers)
        global_server = JitsiServer.objects.create(url="https://jitsi-global.example.com", app_id="global")

        # 2. Organizer-scoped server (scoped to sample_event.organizer)
        orga_server = JitsiServer.objects.create(url="https://jitsi-orga.example.com", app_id="orga")
        orga_server.organizers.add(sample_event.organizer)

        # 3. Multi-event scoped server (scoped to sample_event and event2)
        multi_event_server = JitsiServer.objects.create(url="https://jitsi-multievent.example.com", app_id="multievent")
        multi_event_server.events.add(sample_event, event2)

    # Test is_server_available_for_event
    assert is_server_available_for_event(global_server, sample_event) is True
    assert is_server_available_for_event(global_server, event2) is True
    assert is_server_available_for_event(orga_server, sample_event) is True
    assert is_server_available_for_event(orga_server, event3) is True
    assert is_server_available_for_event(orga_server, event2) is False
    assert is_server_available_for_event(multi_event_server, sample_event) is True
    assert is_server_available_for_event(multi_event_server, event2) is True
    assert is_server_available_for_event(multi_event_server, event3) is False

    # Priority routing:
    # sample_event matches multi_event_server (event-scoped Tier 1)
    chosen = _choose_any_available_server(JitsiServer.objects.filter(active=True), sample_event)
    assert chosen.url == multi_event_server.url

    # event3 matches orga_server (organizer-scoped Tier 2)
    chosen_e3 = _choose_any_available_server(JitsiServer.objects.filter(active=True), event3)
    assert chosen_e3.url == orga_server.url

    # Unscoped event4 falls back to global_server (Tier 3)
    with scopes_disabled():
        org3 = Organizer.objects.create(name="Unscoped Org", slug="unscoped-org")
        event4 = Event.objects.create(organizer=org3, name="Event 4", slug="event-4", date_from=now())
    chosen_e4 = _choose_any_available_server(JitsiServer.objects.filter(active=True), event4)
    assert chosen_e4.url == global_server.url


@pytest.mark.django_db
def test_attendee_side_account_with_team_permission_gets_only_attendee_traits(sample_event, admin_user):
    from eventyay.base.services.user import login
    from eventyay.core.permissions import Permission
    from eventyay.base.models import Room
    from eventyay.eventyay_common.video.permissions import video_attendee_trait

    room = Room.objects.create(
        event=sample_event,
        name="Test Call Room",
        module_config=[{"type": "call.jitsi", "config": {}}],
    )

    mod_perms = [
        Permission.ROOM_JITSI_MODERATE,
        Permission.ROOM_UPDATE,
        Permission.EVENT_UPDATE,
    ]

    admin_user.is_superuser = True
    admin_user.save()

    # 1. Login with is_organizer=False (Attendee side)
    attendee_login = login(
        event=sample_event,
        platform_user=admin_user,
        is_organizer=False,
    )
    attendee_user = attendee_login.user
    expected_attendee_traits = {"attendee", video_attendee_trait(sample_event.slug)}
    assert set(attendee_user.traits) == expected_attendee_traits
    assert "admin" not in attendee_user.traits
    assert not any(t.endswith("-organizer") or t.endswith("-moderator") for t in attendee_user.traits)

    # Must NOT have moderator privileges on attendee side
    assert sample_event.has_permission(user=attendee_user, permission=mod_perms, room=room) is False

    # 2. Login with is_organizer=True (Organizer side)
    organizer_login = login(
        event=sample_event,
        platform_user=admin_user,
        is_organizer=True,
    )
    organizer_user = organizer_login.user
    assert "admin" in organizer_user.traits or any(t.endswith("-organizer") for t in organizer_user.traits)
    assert sample_event.has_permission(user=organizer_user, permission=mod_perms, room=room) is True

    # 3. If organizer subsequently connects on attendee side, they get only attendee traits
    attendee_relogin = login(
        event=sample_event,
        platform_user=admin_user,
        is_organizer=False,
    )
    assert set(attendee_relogin.user.traits) == expected_attendee_traits
    assert "admin" not in attendee_relogin.user.traits
    assert sample_event.has_permission(user=attendee_relogin.user, permission=mod_perms, room=room) is False



