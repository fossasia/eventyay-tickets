from enum import Enum


class Permission(Enum):
    EVENT_VIEW = "event.view"
    EVENT_UPDATE = "event.update"
    EVENT_ANNOUNCE = "event:announce"
    EVENT_SECRETS = "event:secrets"
    EVENT_API = "event:api"
    EVENT_GRAPHS = "event:graphs"
    EVENT_ROOMS_CREATE_STAGE = "event:rooms.create.stage"
    EVENT_ROOMS_CREATE_CHAT = "event:rooms.create.chat"
    EVENT_ROOMS_CREATE_BBB = "event:rooms.create.bbb"
    EVENT_ROOMS_CREATE_JITSI = "event:rooms.create.jitsi"
    EVENT_USERS_LIST = "event:users.list"
    EVENT_USERS_MANAGE = "event:users.manage"
    EVENT_KIOSKS_MANAGE = "event:kiosks.manage"
    EVENT_CHAT_DIRECT = "event:chat.direct"
    EVENT_CONNECTIONS_UNLIMITED = "event:connections.unlimited"
    ROOM_ANNOUNCE = "room:announce"
    ROOM_VIEW = "room:view"
    ROOM_UPDATE = "room:update"
    ROOM_DELETE = "room:delete"
    ROOM_CHAT_READ = "room:chat.read"
    ROOM_CHAT_JOIN = "room:chat.join"
    ROOM_CHAT_SEND = "room:chat.send"
    ROOM_VIEWERS = "room:viewers"
    ROOM_INVITE = "room:invite"
    ROOM_INVITE_ANONYMOUS = "room:invite.anonymous"
    ROOM_CHAT_MODERATE = "room:chat.moderate"
    ROOM_JANUSCALL_JOIN = "room:januscall.join"
    ROOM_JANUSCALL_MODERATE = "room:januscall.moderate"
    ROOM_BBB_JOIN = "room:bbb.join"
    ROOM_BBB_MODERATE = "room:bbb.moderate"
    ROOM_BBB_RECORDINGS = "room:bbb.recordings"
    ROOM_JITSI_JOIN = "room:jitsi.join"
    ROOM_JITSI_MODERATE = "room:jitsi.moderate"
    ROOM_ZOOM_JOIN = "room:zoom.join"
    ROOM_QUESTION_READ = "room:question.read"
    ROOM_QUESTION_ASK = "room:question.ask"
    ROOM_QUESTION_VOTE = "room:question.vote"
    ROOM_QUESTION_MODERATE = "room:question.moderate"
    ROOM_ROULETTE_JOIN = "room:roulette.join"
    ROOM_POLL_READ = "room:poll.read"
    ROOM_POLL_EARLY_RESULTS = "room:poll.early_results"
    ROOM_POLL_VOTE = "room:poll.vote"
    ROOM_POLL_MANAGE = "room:poll.manage"


MAX_PERMISSIONS_IF_SILENCED = {
    Permission.EVENT_VIEW,
    Permission.ROOM_VIEW,
    Permission.ROOM_CHAT_READ,
    Permission.ROOM_CHAT_JOIN,
}


# Consolidated organizer roles (mapped from team dashboard toggles).
VIDEO_CONTENT_MANAGER_PERMISSIONS = [
    Permission.EVENT_ROOMS_CREATE_STAGE.value,
    Permission.EVENT_ROOMS_CREATE_CHAT.value,
    Permission.EVENT_ROOMS_CREATE_BBB.value,
    Permission.EVENT_ROOMS_CREATE_JITSI.value,
    Permission.ROOM_UPDATE.value,
    Permission.ROOM_DELETE.value,
]

VIDEO_MODERATOR_PERMISSIONS = [
    Permission.EVENT_ANNOUNCE.value,
    Permission.ROOM_ANNOUNCE.value,
    Permission.EVENT_USERS_LIST.value,
    Permission.EVENT_USERS_MANAGE.value,
    Permission.ROOM_CHAT_MODERATE.value,
    Permission.ROOM_VIEWERS.value,
    Permission.ROOM_BBB_RECORDINGS.value,
    Permission.ROOM_JITSI_JOIN.value,
    Permission.ROOM_JITSI_MODERATE.value,
    Permission.ROOM_QUESTION_READ.value,
    Permission.ROOM_QUESTION_MODERATE.value,
    Permission.ROOM_POLL_READ.value,
    Permission.ROOM_POLL_MANAGE.value,
    Permission.ROOM_POLL_EARLY_RESULTS.value,
]

VIDEO_KIOSK_MANAGER_PERMISSIONS = [
    Permission.EVENT_KIOSKS_MANAGE.value,
]

VIDEO_ANALYST_PERMISSIONS = [
    Permission.EVENT_GRAPHS.value,
]

VIDEO_CONFIG_MANAGER_PERMISSIONS = [
    Permission.EVENT_UPDATE.value,
]

VIDEO_ROLE_PERMISSIONS: dict[str, list[str]] = {
    'video_content_manager': VIDEO_CONTENT_MANAGER_PERMISSIONS,
    'video_moderator': VIDEO_MODERATOR_PERMISSIONS,
    'video_kiosk_manager': VIDEO_KIOSK_MANAGER_PERMISSIONS,
    'video_analyst': VIDEO_ANALYST_PERMISSIONS,
    'video_config_manager': VIDEO_CONFIG_MANAGER_PERMISSIONS,
}

# Pre-consolidation roles kept for in-flight JWTs / trait grants.
LEGACY_VIDEO_ROLE_PERMISSIONS: dict[str, list[str]] = {
    'video_stage_manager': [
        Permission.EVENT_ROOMS_CREATE_STAGE.value,
    ],
    'video_channel_manager': [
        Permission.EVENT_ROOMS_CREATE_CHAT.value,
        Permission.EVENT_ROOMS_CREATE_BBB.value,
        Permission.EVENT_ROOMS_CREATE_JITSI.value,
    ],
    'video_announcement_manager': [
        Permission.EVENT_ANNOUNCE.value,
    ],
    'video_user_viewer': [
        Permission.EVENT_USERS_LIST.value,
    ],
    'video_user_moderator': [
        Permission.EVENT_USERS_MANAGE.value,
        Permission.ROOM_CHAT_MODERATE.value,
    ],
    'video_room_manager': [
        Permission.ROOM_UPDATE.value,
        Permission.ROOM_DELETE.value,
    ],
    'video_poll_question_manager': [
        Permission.ROOM_QUESTION_READ.value,
        Permission.ROOM_QUESTION_MODERATE.value,
        Permission.ROOM_POLL_READ.value,
        Permission.ROOM_POLL_MANAGE.value,
        Permission.ROOM_POLL_EARLY_RESULTS.value,
    ],
}

LEGACY_VIDEO_ROLE_NAMES: tuple[str, ...] = tuple(LEGACY_VIDEO_ROLE_PERMISSIONS)

SYSTEM_ROLES = {
    '__kiosk': [
        Permission.EVENT_VIEW.value,
        Permission.ROOM_VIEW.value,
        Permission.ROOM_CHAT_READ.value,
        Permission.ROOM_QUESTION_READ.value,
        Permission.ROOM_POLL_READ.value,
        Permission.ROOM_POLL_EARLY_RESULTS.value,
        Permission.ROOM_VIEWERS.value,
        Permission.ROOM_INVITE_ANONYMOUS.value,
    ],
    '__anonymous_event': [
        Permission.EVENT_VIEW.value,
    ],
    '__anonymous_room': [
        Permission.ROOM_QUESTION_READ.value,
        Permission.ROOM_QUESTION_ASK.value,
        Permission.ROOM_QUESTION_VOTE.value,
        Permission.ROOM_POLL_READ.value,
        Permission.ROOM_POLL_VOTE.value,
        Permission.ROOM_VIEW.value,
    ],
    **{name: list(perms) for name, perms in VIDEO_ROLE_PERMISSIONS.items()},
    **{name: list(perms) for name, perms in LEGACY_VIDEO_ROLE_PERMISSIONS.items()},
}

# Roles that are considered organizer/admin roles for permission management
ORGANIZER_ROLES = frozenset(
    {
        'admin',
        'apiuser',
        'scheduleuser',
        'moderator',
        'room_creator',
        *VIDEO_ROLE_PERMISSIONS,
        *LEGACY_VIDEO_ROLE_PERMISSIONS,
    }
)


def default_roles():
    """Shared Event/World role → permission map (single source of truth)."""
    attendee = [
        Permission.EVENT_VIEW,
        Permission.EVENT_CHAT_DIRECT,
    ]
    viewer = attendee + [Permission.ROOM_VIEW, Permission.ROOM_CHAT_READ]
    participant = viewer + [
        Permission.ROOM_CHAT_JOIN,
        Permission.ROOM_CHAT_SEND,
        Permission.ROOM_QUESTION_READ,
        Permission.ROOM_QUESTION_ASK,
        Permission.ROOM_QUESTION_VOTE,
        Permission.ROOM_POLL_READ,
        Permission.ROOM_POLL_VOTE,
        Permission.ROOM_ROULETTE_JOIN,
        Permission.ROOM_BBB_JOIN,
        Permission.ROOM_JANUSCALL_JOIN,
        Permission.ROOM_JITSI_JOIN,
        Permission.ROOM_ZOOM_JOIN,
    ]
    room_creator = [Permission.EVENT_ROOMS_CREATE_CHAT]
    room_owner = participant + [
        Permission.ROOM_INVITE,
        Permission.ROOM_DELETE,
        Permission.ROOM_JITSI_MODERATE,
    ]
    speaker = participant + [
        Permission.ROOM_BBB_MODERATE,
        Permission.ROOM_JANUSCALL_MODERATE,
        Permission.ROOM_POLL_EARLY_RESULTS,
    ]
    moderator = speaker + [
        Permission.ROOM_VIEWERS,
        Permission.ROOM_CHAT_MODERATE,
        Permission.ROOM_ANNOUNCE,
        Permission.ROOM_BBB_RECORDINGS,
        Permission.ROOM_JITSI_MODERATE,
        Permission.ROOM_QUESTION_MODERATE,
        Permission.ROOM_POLL_EARLY_RESULTS,
        Permission.ROOM_POLL_MANAGE,
        Permission.EVENT_ANNOUNCE,
    ]
    admin = (
        moderator
        + room_creator
        + [
            Permission.EVENT_UPDATE,
            Permission.ROOM_DELETE,
            Permission.ROOM_UPDATE,
            Permission.ROOM_INVITE,
            Permission.EVENT_ROOMS_CREATE_BBB,
            Permission.EVENT_ROOMS_CREATE_JITSI,
            Permission.EVENT_ROOMS_CREATE_STAGE,
            Permission.EVENT_USERS_LIST,
            Permission.EVENT_USERS_MANAGE,
            Permission.EVENT_KIOSKS_MANAGE,
            Permission.EVENT_GRAPHS,
            Permission.EVENT_CONNECTIONS_UNLIMITED,
        ]
    )
    apiuser = admin + [Permission.EVENT_API, Permission.EVENT_SECRETS]
    scheduleuser = [Permission.EVENT_API]
    roles = {
        'attendee': attendee,
        'viewer': viewer,
        'participant': participant,
        'room_creator': room_creator,
        'room_owner': room_owner,
        'speaker': speaker,
        'moderator': moderator,
        'admin': admin,
        'apiuser': apiuser,
        'scheduleuser': scheduleuser,
    }
    roles.update({name: list(perms) for name, perms in VIDEO_ROLE_PERMISSIONS.items()})
    return roles


def default_grants():
    return {
        'attendee': ['attendee'],
        'admin': ['admin'],
        'scheduleuser': [],
    }


def normalize_permission_value(permission):
    """Normalize permission to string value for comparison.

    Args:
        permission: Permission enum or string value

    Returns:
        str: Permission value as string

    Raises:
        TypeError: If permission is not a string or Permission enum
    """
    if isinstance(permission, Permission):
        val = permission.value
    elif isinstance(permission, str):
        val = permission
    else:
        raise TypeError(
            f"Expected str or Permission enum, got {type(permission).__name__}"
        )
    if val == "world:view":
        return "event.view"
    if val == "world:update":
        return "event.update"
    if val.startswith("world:"):
        return "event:" + val[len("world:"):]
    return val


def traits_match_required(traits: list[str], required_traits: list) -> bool:
    """Check if user traits match required traits for a role.

    Args:
        traits: List of user traits
        required_traits: List of required traits (can contain nested lists for OR logic)

    Returns:
        bool: True if all required traits are matched
    """
    if not isinstance(required_traits, list):
        return False

    return all(
        any(x in traits for x in (r if isinstance(r, list) else [r]))
        for r in required_traits
    )
