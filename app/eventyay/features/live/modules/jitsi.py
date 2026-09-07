import logging
import time

import jwt
from channels.db import database_sync_to_async

from eventyay.base.services.jitsi import (
    JitsiServerUnavailable,
    choose_server_for_room,
    normalize_server_url,
)
from eventyay.core.permissions import Permission
from eventyay.features.live.decorators import command, room_action
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.base import BaseModule


logger = logging.getLogger(__name__)

JITSI_PARTICIPANT_TOOLBAR_BUTTONS = [
    "camera",
    "microphone",
    "desktop",
    "chat",
    "raisehand",
    "participants-pane",
    "tileview",
    "select-background",
    "settings",
    "fullscreen",
    "videoquality",
    "hangup",
]

JITSI_MODERATOR_TOOLBAR_BUTTONS = [
    "camera",
    "microphone",
    "desktop",
    "chat",
    "raisehand",
    "participants-pane",
    "tileview",
    "select-background",
    "mute-everyone",
    "mute-video-everyone",
    "recording",
    "livestreaming",
    "settings",
    "fullscreen",
    "videoquality",
    "hangup",
]

JITSI_INTERFACE_CONFIG_OVERWRITE = {
    "APP_NAME": "Eventyay Video",
    "NATIVE_APP_NAME": "Eventyay Video",
    "PROVIDER_NAME": "Eventyay",
    "BRAND_WATERMARK_LINK": "",
    "DEFAULT_LOGO_URL": "",
    "DEFAULT_WELCOME_PAGE_LOGO_URL": "",
    "JITSI_WATERMARK_LINK": "",
    "SHOW_BRAND_WATERMARK": False,
    "SHOW_CHROME_EXTENSION_BANNER": False,
    "SHOW_JITSI_WATERMARK": False,
    "SHOW_POWERED_BY": False,
    "SHOW_WATERMARK_FOR_GUESTS": False,
    "SHOW_PROMOTIONAL_CLOSE_PAGE": False,
    "HIDE_DEEP_LINKING_LOGO": True,
    "GENERATE_ROOMNAMES_ON_WELCOME_PAGE": False,
    "RECENT_LIST_ENABLED": False,
    "TOOLBAR_ALWAYS_VISIBLE": False,
    "DISABLE_VIDEO_BACKGROUND": True,
    "DISABLE_JOIN_LEAVE_NOTIFICATIONS": False,
}

JITSI_JWT_LIFETIME_SECONDS = 10 * 60


def normalize_jitsi_room_name(event_id, room_id):
    return f"event-{event_id}-room-{room_id}"


def get_jitsi_room_display_name(room):
    return str(room.name or "room")


def get_safe_avatar_url(profile):
    if not isinstance(profile, dict):
        return ""
    raw = profile.get("avatar")
    if isinstance(raw, dict):
        return str(raw.get("url") or "")
    if isinstance(raw, str):
        return raw.strip()
    return ""


def build_jitsi_config_overwrite(
    module_config,
    is_moderator,
    room_display_name=None,
    has_jwt=False,
):
    start_audio_muted = bool(
        module_config.get("start_with_audio_muted") or module_config.get("auto_mute")
    )
    start_video_muted = bool(
        module_config.get("start_with_video_muted")
    )
    waiting_room = bool(
        module_config.get("waiting_room") or module_config.get("enable_lobby")
    )
    record = bool(module_config.get("record", False))
    livestreaming = bool(module_config.get("livestreaming", False))
    disable_cam = bool(module_config.get("disable_cam"))
    disable_chat = bool(module_config.get("disable_chat"))
    require_display_name = bool(module_config.get("require_display_name"))

    config_overwrite = {
        "startWithAudioMuted": start_audio_muted,
        "startWithVideoMuted": start_video_muted or (disable_cam and not is_moderator),
        "enableUserRolesBasedOnToken": bool(has_jwt),
        "tokenAuthUrl": None,
        "securityUi": {"hideLobbyButton": not is_moderator, "disablePassword": True},
        "readOnlyName": not require_display_name,
        "enableClosePage": False,
        "disableInviteFunctions": True,
        "disablePolls": True,
        "disableThirdPartyRequests": True,
        "defaultRemoteDisplayName": "Attendee",
        "hideConferenceTimer": False,
        "hiddenPremeetingButtons": ["invite"],
        "disableSelfView": False,
        "fileRecordingsEnabled": record if is_moderator else False,
        "liveStreamingEnabled": livestreaming if is_moderator else False,
        "toolbarConfig": {"alwaysVisible": False, "timeout": 4000},
        "filmstrip": {"disableResizable": False},
        "breakoutRooms": {
            "hideAddRoomButton": True,
            "hideAutoAssignButton": True,
            "hideJoinRoomButton": not is_moderator,
        },
        "remoteVideoMenu": {
            "disableKick": not is_moderator,
            "disableGrantModerator": not is_moderator,
            "disablePrivateChat": False,
        },
        "prejoinPageEnabled": require_display_name,
        "prejoinConfig": {"enabled": require_display_name},
        "requireDisplayName": require_display_name,
        "enableLobby": True,
        "lobby": {"enable": waiting_room},
        "disableDeepLinking": True,
        "enableWelcomePage": False,
        "welcomePage": {"disabled": True},
        "doNotStoreRoom": True,
        "whiteboard": {"enabled": False},
    }
    if room_display_name:
        config_overwrite["subject"] = room_display_name
    if is_moderator:
        mod_buttons = list(JITSI_MODERATOR_TOOLBAR_BUTTONS)
        if not record and "recording" in mod_buttons:
            mod_buttons.remove("recording")
        if not livestreaming and "livestreaming" in mod_buttons:
            mod_buttons.remove("livestreaming")
        config_overwrite["toolbarButtons"] = mod_buttons
    if not is_moderator:
        part_buttons = list(JITSI_PARTICIPANT_TOOLBAR_BUTTONS)
        if disable_cam and "camera" in part_buttons:
            part_buttons.remove("camera")
        if disable_chat and "chat" in part_buttons:
            part_buttons.remove("chat")
        config_overwrite.update(
            {
                "fileRecordingsEnabled": False,
                "liveStreamingEnabled": False,
                "disableRemoteMute": True,
                "disableModeratorIndicator": True,
                "disableChat": disable_chat,
                "securityUi": {"hideLobbyButton": True, "disablePassword": True},
                "remoteVideoMenu": {
                    "disableKick": True,
                    "disableGrantModerator": True,
                    "disablePrivateChat": False,
                },
                "participantsPane": {
                    "hideModeratorSettingsTab": True,
                    "hideMoreActionsButton": True,
                    "hideMuteAllButton": True,
                },
                "breakoutRooms": {
                    **config_overwrite["breakoutRooms"],
                    "hideAddRoomButton": True,
                    "hideAutoAssignButton": True,
                    "hideJoinRoomButton": True,
                    "hideModeratorSettingsTab": True,
                    "hideMoreActionsButton": True,
                    "hideMuteAllButton": True,
                },
                "toolbarButtons": part_buttons,
            }
        )
    return config_overwrite


def build_jitsi_interface_config_overwrite():
    return dict(JITSI_INTERFACE_CONFIG_OVERWRITE)


class JitsiModule(BaseModule):
    prefix = "jitsi"

    async def can_moderate_room(self) -> bool:
        """
        Map Eventyay user moderation permissions to room moderator status.
        Checks if the user holds room moderation permission, or event/room
        administrative update rights.
        """
        return bool(
            await self.consumer.event.has_permission_async(
                user=self.consumer.user,
                permission=[
                    Permission.ROOM_JITSI_MODERATE,
                    Permission.ROOM_UPDATE,
                    Permission.EVENT_UPDATE,
                ],
                room=self.room,
            )
        )

    @command("room_config")
    @room_action(
        permission_required=Permission.ROOM_JITSI_JOIN,
        module_required="call.jitsi",
    )
    async def room_config(self, body):
        display_name = (
            (self.consumer.user.profile or {}).get("display_name")
            or getattr(self.consumer.user, "fullname", None)
            or (self.consumer.user.email.split("@")[0] if getattr(self.consumer.user, "email", None) else None)
            or "Attendee"
        )
        if hasattr(self.consumer.user, "profile") and isinstance(self.consumer.user.profile, dict):
            if not self.consumer.user.profile.get("display_name"):
                self.consumer.user.profile["display_name"] = display_name
        elif not getattr(self.consumer.user, "profile", None):
            self.consumer.user.profile = {"display_name": display_name}

        try:
            server_model = await database_sync_to_async(choose_server_for_room)(
                room=self.room,
                prefer_server=self.module_config.get("prefer_server"),
            )
            if server_model is None:
                raise JitsiServerUnavailable
        except JitsiServerUnavailable:
            raise ConsumerException("jitsi.server_unavailable")

        server = normalize_server_url(server_model.url)
        domain = server["domain"] if server else None
        room_name = normalize_jitsi_room_name(self.consumer.event.id, self.room.id)
        room_display_name = get_jitsi_room_display_name(self.room)
        if not domain:
            raise ConsumerException("jitsi.missing_domain")

        is_moderator = await self.can_moderate_room()
        logger.info(
            "Jitsi room_config user=%s room=%s jitsi_room=%s moderator=%s domain=%s server=%s",
            self.consumer.user.pk,
            self.room.id,
            room_name,
            is_moderator,
            domain,
            server_model.pk,
        )

        has_jwt = bool(server_model.app_id and server_model.app_secret)
        jwt_token = None
        if has_jwt:
            jwt_token = self._build_jwt(
                server=server_model,
                domain=domain,
                room_name=room_name,
                display_name=display_name,
                is_moderator=is_moderator,
            )

        user_email = (
            getattr(self.consumer.user, "email", "")
            or (self.consumer.user.profile or {}).get("email")
            or ""
        )
        user_avatar = get_safe_avatar_url(self.consumer.user.profile)

        result = {
            "domain": domain,
            "url": server["url"],
            "protocol": server["protocol"],
            "roomName": room_name,
            "roomDisplayName": room_display_name,
            "userInfo": {
                "displayName": display_name,
                "email": user_email,
                "avatar": user_avatar,
            },
            "configOverwrite": build_jitsi_config_overwrite(
                self.module_config,
                is_moderator,
                room_display_name,
                has_jwt=has_jwt,
            ),
            "interfaceConfigOverwrite": build_jitsi_interface_config_overwrite(),
            "moderator": is_moderator,
            "jwt": jwt_token,
        }

        await self.consumer.send_success(result)

    def _build_jwt(
        self,
        server,
        domain,
        room_name,
        display_name,
        is_moderator,
    ):
        app_id = server.app_id
        app_secret = server.app_secret
        if not app_id or not app_secret:
            raise ConsumerException("jitsi.missing_jwt_config")

        now = int(time.time())
        user_email = (
            getattr(self.consumer.user, "email", "")
            or (self.consumer.user.profile or {}).get("email")
            or ""
        )
        user_avatar = get_safe_avatar_url(self.consumer.user.profile)
        payload = {
            "aud": "jitsi",
            "iss": app_id,
            "sub": "*",
            "room": room_name,
            "nbf": now - 10,
            "exp": now + JITSI_JWT_LIFETIME_SECONDS,
            "context": {
                "user": {
                    "id": str(self.consumer.user.pk),
                    "name": display_name,
                    "email": user_email,
                    "avatar": user_avatar,
                    "moderator": bool(is_moderator),
                    "affiliation": "owner" if is_moderator else "member",
                },
                "features": {
                    "livestreaming": bool(is_moderator and self.module_config.get("livestreaming", False)),
                    "recording": bool(is_moderator and self.module_config.get("record", False)),
                    "transcription": bool(is_moderator and self.module_config.get("transcription", False)),
                    "outbound-call": False,
                },
            },
        }
        headers = {}
        if server.key_id:
            headers["kid"] = server.key_id
        return jwt.encode(payload, app_secret, algorithm="HS256", headers=headers)
