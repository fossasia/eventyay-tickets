from unittest.mock import MagicMock
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
import pytest

from eventyay.multidomain.views import VideoAdminRedirectView, VideoSPAView


def test_video_admin_redirect_view():
    factory = RequestFactory()
    request = factory.get('/video/admin/rooms?tab=all')
    view = VideoAdminRedirectView.as_view()
    response = view(request, organizer='demo-org', event='demo-event', subpath='rooms')
    assert response.status_code == 302
    assert response['Location'] == '/video/event/demo-org/demo-event/rooms?tab=all'


def test_video_admin_redirect_view_root():
    factory = RequestFactory()
    request = factory.get('/video/admin/')
    view = VideoAdminRedirectView.as_view()
    response = view(request, organizer='demo-org', event='demo-event')
    assert response.status_code == 302
    assert response['Location'] == '/video/event/demo-org/demo-event/'


def test_video_spa_view_unauthenticated_organizer_redirects_to_login(monkeypatch):
    factory = RequestFactory()
    request = factory.get('/video/event/demo-org/demo-event/')
    request.user = MagicMock()
    request.user.is_authenticated = False

    fake_event = MagicMock()
    fake_event.slug = 'demo-event'
    fake_event.organizer.slug = 'demo-org'

    monkeypatch.setattr(
        'eventyay.multidomain.views.Event.objects.select_related',
        lambda *args: MagicMock(get=lambda **kwargs: fake_event),
    )

    view = VideoSPAView.as_view(is_organizer=True)
    response = view(request, organizer='demo-org', event='demo-event')
    assert response.status_code == 302
    assert '/login' in response['Location'] or 'login' in response['Location']


def test_video_spa_view_unauthorized_organizer_raises_permission_denied(monkeypatch):
    factory = RequestFactory()
    request = factory.get('/video/event/demo-org/demo-event/')
    request.user = MagicMock()
    request.user.is_authenticated = True
    request.user.is_staff = False
    request.user.is_superuser = False
    request.user.has_event_permission.return_value = False
    request.user.has_organizer_permission.return_value = False

    fake_event = MagicMock()
    fake_event.slug = 'demo-event'
    fake_event.organizer.slug = 'demo-org'

    monkeypatch.setattr(
        'eventyay.multidomain.views.Event.objects.select_related',
        lambda *args: MagicMock(get=lambda **kwargs: fake_event),
    )

    view = VideoSPAView.as_view(is_organizer=True)
    with pytest.raises(PermissionDenied):
        view(request, organizer='demo-org', event='demo-event')


def test_get_user_with_platform_user(monkeypatch):
    from eventyay.base.services.user import get_user

    fake_event = MagicMock()
    fake_event.id = 1
    fake_event.slug = 'demo-event'
    fake_event.organizer = MagicMock()
    fake_event.organizer.slug = 'demo-org'

    fake_platform_user = MagicMock()
    fake_platform_user.email = 'organizer@example.com'
    fake_platform_user.fullname = 'Demo Organizer'
    fake_platform_user.is_staff = True
    fake_platform_user.get_event_permission_set.return_value = {'can_change_event_settings'}

    fake_video_user = MagicMock()
    fake_video_user.id = 'user-123'
    fake_video_user.traits = ['admin']

    monkeypatch.setattr('eventyay.eventyay_common.video.traits_sync.apply_live_team_video_traits', lambda event, token_id, traits, **kwargs: traits)
    monkeypatch.setattr('eventyay.base.services.user.get_user_by_token_id', lambda event_id, token_id: fake_video_user)
    monkeypatch.setattr('eventyay.base.services.user.get_user_by_id', lambda event_id, user_id: fake_video_user)
    monkeypatch.setattr('eventyay.base.services.user.update_user', lambda event_id, id, **kwargs: fake_video_user)
    monkeypatch.setattr('eventyay.base.services.user.apply_video_jwt_contact_to_profile', lambda user, event_id, token_id: None)

    user = get_user(fake_event, with_platform_user=fake_platform_user)
    assert user == fake_video_user


def test_video_announcements_live_feature_default():
    from eventyay.base.services.event import _config_serializer

    fake_event = MagicMock()
    fake_event.id = 1
    fake_event.slug = 'demo-event'
    fake_event.config = {'live_features': {'chat_rooms': True}}
    fake_event.locale = 'en'
    fake_event.roles = {}
    fake_event.trait_grants = {}
    fake_event.timezone = 'UTC'

    data = _config_serializer(fake_event).data
    assert data['live_features']['announcements'] is True
    assert data['live_features']['chat_rooms'] is True


@pytest.mark.asyncio
async def test_announcement_module_disabled_check():
    from unittest.mock import AsyncMock
    from eventyay.features.live.modules.announcement import AnnouncementModule

    fake_consumer = MagicMock()
    fake_consumer.user = MagicMock()
    fake_consumer.event = MagicMock()
    fake_consumer.event.has_permission_async = AsyncMock(return_value=True)
    fake_consumer.event.config = {'live_features': {'announcements': False}}
    fake_consumer.send_error = AsyncMock()

    module = AnnouncementModule(fake_consumer)
    await module.create_announcement({'text': 'Hello'})
    fake_consumer.send_error.assert_called_once_with(code='announcements.disabled')


def test_video_permission_definitions_mapping():
    from eventyay.eventyay_common.video.permissions import (
        collect_user_video_traits,
        VIDEO_PERMISSION_DEFINITIONS,
    )

    slug = 'test-conf'
    # Test individual permissions
    traits = collect_user_video_traits(slug, ['can_video_manage_content'])
    assert traits == [f'eventyay-video-event-{slug}-video-content-manager']

    traits = collect_user_video_traits(slug, ['can_video_moderate'])
    assert traits == [f'eventyay-video-event-{slug}-video-moderator']

    traits = collect_user_video_traits(slug, ['can_video_manage_kiosks'])
    assert traits == [f'eventyay-video-event-{slug}-video-kiosk-manager']

    traits = collect_user_video_traits(slug, ['can_video_view_analytics'])
    assert traits == [f'eventyay-video-event-{slug}-video-analyst']

    traits = collect_user_video_traits(slug, ['can_change_config'])
    assert traits == [f'eventyay-video-event-{slug}-video-config-manager']

    traits = collect_user_video_traits(slug, ['can_change_event_settings'])
    assert traits == []

    # Non-video permissions yield no video traits
    traits = collect_user_video_traits(slug, ['can_change_submissions', 'can_view_orders', 'can_change_event_settings'])
    assert traits == []


def test_apply_live_team_video_traits_no_video_permissions(monkeypatch):
    from eventyay.eventyay_common.video.traits_sync import apply_live_team_video_traits

    fake_event = MagicMock()
    fake_event.slug = 'demo-event'
    fake_event.organizer = MagicMock()

    fake_platform_user = MagicMock()
    fake_platform_user.is_staff = True  # Staff user, but no active staff session!
    fake_platform_user.is_superuser = False
    fake_platform_user.has_active_staff_session.return_value = False
    fake_platform_user.get_event_permission_set.return_value = {'can_change_submissions'}

    monkeypatch.setattr(
        'eventyay.base.services.user.resolve_account_fields_by_token_ids',
        lambda ids: {'token123': {'email': 'user@example.com'}},
    )
    monkeypatch.setattr(
        'eventyay.base.services.user._ticket_lookup',
        lambda accounts, tid: {'email': 'user@example.com'},
    )
    monkeypatch.setattr(
        'eventyay.eventyay_common.video.traits_sync.User.objects.filter',
        lambda **kwargs: MagicMock(order_by=lambda *args: MagicMock(first=lambda: fake_platform_user)),
    )

    initial_traits = ['attendee', 'eventyay-video-event-demo-event', 'eventyay-video-event-demo-event-organizer', 'admin']
    result = apply_live_team_video_traits(fake_event, 'token123', initial_traits)

    # 'admin' must be removed, and no video managed traits added
    assert 'admin' not in result
    assert f'eventyay-video-event-demo-event-video-content-manager' not in result
    assert f'eventyay-video-event-demo-event-video-moderator' not in result
    assert f'eventyay-video-event-demo-event-video-kiosk-manager' not in result
    assert f'eventyay-video-event-demo-event-video-analyst' not in result
    assert f'eventyay-video-event-demo-event-video-config-manager' not in result
    assert result == ['attendee', 'eventyay-video-event-demo-event', 'eventyay-video-event-demo-event-organizer']


def test_apply_live_team_video_traits_with_active_staff_session(monkeypatch):
    from eventyay.eventyay_common.video.traits_sync import apply_live_team_video_traits

    fake_event = MagicMock()
    fake_event.slug = 'demo-event'
    fake_event.organizer = MagicMock()

    fake_platform_user = MagicMock()
    fake_platform_user.is_staff = True
    fake_platform_user.is_superuser = False
    fake_platform_user.has_active_staff_session.return_value = True
    fake_platform_user.get_event_permission_set.return_value = set()

    monkeypatch.setattr(
        'eventyay.base.services.user.resolve_account_fields_by_token_ids',
        lambda ids: {'token123': {'email': 'user@example.com'}},
    )
    monkeypatch.setattr(
        'eventyay.base.services.user._ticket_lookup',
        lambda accounts, tid: {'email': 'user@example.com'},
    )
    monkeypatch.setattr(
        'eventyay.eventyay_common.video.traits_sync.User.objects.filter',
        lambda **kwargs: MagicMock(order_by=lambda *args: MagicMock(first=lambda: fake_platform_user)),
    )

    initial_traits = ['attendee', 'eventyay-video-event-demo-event', 'eventyay-video-event-demo-event-organizer']
    result = apply_live_team_video_traits(fake_event, 'token123', initial_traits)

    assert 'admin' in result


def test_apply_live_team_video_traits_with_direct_platform_user():
    from eventyay.eventyay_common.video.traits_sync import apply_live_team_video_traits

    fake_event = MagicMock()
    fake_event.slug = 'demo-event'
    fake_event.organizer = MagicMock()

    fake_platform_user = MagicMock()
    fake_platform_user.is_staff = False
    fake_platform_user.is_superuser = False
    fake_platform_user.get_event_permission_set.return_value = {'can_video_manage_content', 'can_change_config'}

    initial_traits = ['attendee', 'eventyay-video-event-demo-event', 'eventyay-video-event-demo-event-organizer']
    result = apply_live_team_video_traits(
        fake_event,
        'token123',
        initial_traits,
        platform_user=fake_platform_user,
    )

    assert 'eventyay-video-event-demo-event-video-content-manager' in result
    assert 'eventyay-video-event-demo-event-video-config-manager' in result

    # Verify can_change_event_settings alone does NOT grant video-config-manager
    fake_platform_user.get_event_permission_set.return_value = {'can_change_event_settings'}
    result_settings_only = apply_live_team_video_traits(
        fake_event,
        'token123',
        initial_traits,
        platform_user=fake_platform_user,
    )
    assert 'eventyay-video-event-demo-event-video-config-manager' not in result_settings_only


def test_check_has_active_staff_session_and_is_platform_event_admin():
    from eventyay.eventyay_common.video.traits_sync import (
        check_has_active_staff_session,
        is_platform_event_admin,
    )

    # Anonymous / None user
    assert check_has_active_staff_session(None) is False
    assert is_platform_event_admin(None) is False

    # Regular attendee
    attendee = MagicMock()
    attendee.is_authenticated = True
    attendee.is_staff = False
    attendee.is_superuser = False
    attendee.has_active_staff_session.return_value = False
    assert check_has_active_staff_session(attendee) is False
    assert is_platform_event_admin(attendee) is False

    # Superuser
    superuser = MagicMock()
    superuser.is_authenticated = True
    superuser.is_staff = True
    superuser.is_superuser = True
    superuser.has_active_staff_session.return_value = False
    assert check_has_active_staff_session(superuser) is False
    assert is_platform_event_admin(superuser) is True

    # Staff with active session
    staff_active = MagicMock()
    staff_active.is_authenticated = True
    staff_active.is_staff = True
    staff_active.is_superuser = False
    staff_active.has_active_staff_session.return_value = True
    assert check_has_active_staff_session(staff_active) is True
    assert is_platform_event_admin(staff_active) is True


def test_normalize_permission_value_world_aliases():
    from eventyay.core.permissions import Permission, normalize_permission_value

    assert normalize_permission_value(Permission.EVENT_UPDATE) == 'event.update'
    assert normalize_permission_value('event.update') == 'event.update'
    assert normalize_permission_value('world:update') == 'event.update'
    assert normalize_permission_value(Permission.EVENT_VIEW) == 'event.view'
    assert normalize_permission_value('world:view') == 'event.view'
    assert normalize_permission_value('world:rooms.create.stage') == 'event:rooms.create.stage'
    assert normalize_permission_value(Permission.EVENT_ROOMS_CREATE_STAGE) == 'event:rooms.create.stage'


def test_event_has_permission_with_world_update_in_roles():
    from unittest.mock import MagicMock, PropertyMock, patch
    from eventyay.base.models import Event, User
    from eventyay.core.permissions import Permission

    with patch.object(Event, 'settings', new=MagicMock(get=lambda *a, **kw: False)), \
         patch.object(Event, 'rooms', new_callable=PropertyMock) as mock_rooms:
        mock_rooms.return_value = MagicMock(all=lambda: [])
        event = Event(
            pk=1,
            slug='test-slug',
            trait_grants=None,
            roles={'video_config_manager': ['world:update']},
        )
        fake_user = MagicMock()
        fake_user.is_banned = False
        fake_user.is_silenced = False
        fake_user.type = User.UserType.PERSON
        fake_user.traits = [
            'attendee',
            'eventyay-video-event-test-slug',
            'eventyay-video-event-test-slug-video-config-manager',
        ]

        assert event.has_permission(user=fake_user, permission=Permission.EVENT_UPDATE) is True
        assert event.has_permission(user=fake_user, permission=Permission.EVENT_VIEW) is True


def test_get_event_config_for_user_aliases_world_and_event_update():
    from unittest.mock import MagicMock, PropertyMock, patch
    from eventyay.base.models import Event, User
    from eventyay.base.services.event import get_event_config_for_user

    with patch.object(Event, 'settings', new=MagicMock(get=lambda *a, **kw: None)), \
         patch.object(Event, 'rooms', new_callable=PropertyMock) as mock_rooms:
        mock_rooms.return_value = MagicMock(all=lambda: [])
        event = Event(
            pk=1,
            slug='test-slug',
            config={},
            trait_grants=None,
            roles={'video_config_manager': ['world:update']},
        )
        fake_user = MagicMock()
        fake_user.is_banned = False
        fake_user.is_silenced = False
        fake_user.type = User.UserType.PERSON
        fake_user.traits = [
            'attendee',
            'eventyay-video-event-test-slug',
            'eventyay-video-event-test-slug-video-config-manager',
        ]

        config = get_event_config_for_user(event, fake_user)
        perms = config['permissions']
        assert 'event.update' in perms
        assert 'world:update' in perms
        assert 'event.view' in perms
        assert 'world:view' in perms


@pytest.mark.asyncio
async def test_announcements_disabled_guard():
    from unittest.mock import AsyncMock, MagicMock
    from eventyay.features.live.modules.announcement import AnnouncementModule

    consumer = MagicMock()
    consumer.user = MagicMock()
    consumer.event = MagicMock()
    consumer.event.id = 1
    consumer.event.config = {'live_features': {'announcements': False}}
    consumer.event.has_permission_async = AsyncMock(return_value=True)
    consumer.send_error = AsyncMock()
    consumer.send_success = AsyncMock()

    module = AnnouncementModule(consumer)
    await module.list_announcements({})
    consumer.send_error.assert_awaited_once_with(code='announcements.disabled')
    consumer.send_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_config_get_and_patch_granular_permissions():
    from unittest.mock import AsyncMock, MagicMock, patch
    from eventyay.core.permissions import Permission
    from eventyay.features.live.modules.event import EventModule

    consumer = MagicMock()
    consumer.event = MagicMock()
    consumer.event.id = 1
    consumer.event.config = {'video_player': {'auto_play': True}, 'conftool_password': 'secret_password'}
    consumer.user = MagicMock()
    consumer.send_success = AsyncMock()
    consumer.send_error = AsyncMock()

    # When user only has EVENT_ROOMS_CREATE_STAGE, config.get strips conftool_password
    async def fake_has_perm(user, permission):
        if isinstance(permission, (list, tuple, set)):
            return Permission.EVENT_ROOMS_CREATE_STAGE in permission
        return permission == Permission.EVENT_ROOMS_CREATE_STAGE

    consumer.event.has_permission_async = fake_has_perm

    with patch('eventyay.features.live.modules.event._config_serializer') as mock_serializer:
        mock_serializer.return_value.data = {
            'video_player': {'auto_play': True},
            'conftool_password': 'secret_password',
        }
        module = EventModule(consumer)
        await module.config_get({})
        sent_data = consumer.send_success.call_args[0][0]
        assert 'conftool_password' not in sent_data
        assert sent_data['video_player'] == {'auto_play': True}


def test_ensure_video_configuration_preserves_existing_config():
    from eventyay.eventyay_common.views.event import VideoAccessAuthenticator

    view = VideoAccessAuthenticator()
    fake_request = MagicMock()
    fake_event = MagicMock()
    fake_event.config = {'live_features': {'kiosks': True}, 'track_event_views': False}
    fake_event.settings = MagicMock()
    fake_request.event = fake_event
    view.request = fake_request

    view._ensure_video_configuration()

    assert fake_event.config['live_features'] == {'kiosks': True}
    assert fake_event.config['track_event_views'] is False
    assert 'JWT_secrets' in fake_event.config
    assert len(fake_event.config['JWT_secrets']) == 1


def test_is_announcements_enabled_helper():
    from eventyay.features.live.modules.announcement import is_announcements_enabled

    event_default = MagicMock(config={})
    assert is_announcements_enabled(event_default) is True

    event_enabled = MagicMock(config={'live_features': {'announcements': True}})
    assert is_announcements_enabled(event_enabled) is True

    event_disabled = MagicMock(config={'live_features': {'announcements': False}})
    assert is_announcements_enabled(event_disabled) is False

    event_none_config = MagicMock(config=None)
    assert is_announcements_enabled(event_none_config) is True


@pytest.mark.asyncio
async def test_channel_permission_required_blocks_direct_channel_when_disabled():
    from eventyay.features.live.modules.chat import channel_action
    from eventyay.features.live.exceptions import ConsumerException

    consumer = MagicMock()
    consumer.event = MagicMock()
    consumer.event.config = {'live_features': {'direct_messaging': False}}
    consumer.channel_cache = {}

    class FakeChatModule:
        def __init__(self, consumer):
            self.consumer = consumer
            self.channel = None

        @channel_action()
        async def fake_action(self, body):
            return "ok"

    module = FakeChatModule(consumer)
    direct_channel = MagicMock()
    direct_channel.room = None
    consumer.channel_cache['dm_channel_1'] = direct_channel

    with pytest.raises(ConsumerException) as exc_info:
        await module.fake_action({'channel': 'dm_channel_1'})
    assert exc_info.value.code == 'chat.direct_disabled'


def test_apply_live_team_video_traits_passes_session_key(monkeypatch):
    from eventyay.eventyay_common.video.traits_sync import apply_live_team_video_traits

    fake_event = MagicMock()
    fake_event.slug = 'demo-event'
    fake_event.organizer = MagicMock()

    fake_platform_user = MagicMock()
    fake_platform_user.is_staff = True
    fake_platform_user.is_superuser = False
    fake_platform_user.has_active_staff_session.side_effect = lambda sk: sk == 'valid_session'
    fake_platform_user.get_event_permission_set.return_value = set()

    monkeypatch.setattr(
        'eventyay.base.services.user.resolve_account_fields_by_token_ids',
        lambda ids: {'token123': {'email': 'user@example.com'}},
    )
    monkeypatch.setattr(
        'eventyay.base.services.user._ticket_lookup',
        lambda accounts, tid: {'email': 'user@example.com'},
    )
    monkeypatch.setattr(
        'eventyay.eventyay_common.video.traits_sync.User.objects.filter',
        lambda **kwargs: MagicMock(order_by=lambda *args: MagicMock(first=lambda: fake_platform_user)),
    )

    initial_traits = ['attendee', 'eventyay-video-event-demo-event', 'eventyay-video-event-demo-event-organizer']
    # With wrong session key: admin should NOT be present
    result_wrong = apply_live_team_video_traits(fake_event, 'token123', initial_traits, session_key='wrong_session')
    assert 'admin' not in result_wrong

    # With matching session key: admin should be present
    result_valid = apply_live_team_video_traits(fake_event, 'token123', initial_traits, session_key='valid_session')
    assert 'admin' in result_valid




