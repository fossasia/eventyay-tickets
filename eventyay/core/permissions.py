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
    EVENT_ROOMS_CREATE_EXHIBITION = "event:rooms.create.exhibition"
    EVENT_ROOMS_CREATE_POSTER = "event:rooms.create.poster"
    EVENT_USERS_LIST = "event:users.list"
    EVENT_USERS_MANAGE = "event:users.manage"
    EVENT_CHAT_DIRECT = "event:chat.direct"
    EVENT_EXHIBITION_CONTACT = "event:exhibition.contact"
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


SYSTEM_ROLES = {
    "__kiosk": [
        Permission.EVENT_VIEW.value,
        Permission.ROOM_VIEW.value,
        Permission.ROOM_CHAT_READ.value,
        Permission.ROOM_QUESTION_READ.value,
        Permission.ROOM_POLL_READ.value,
        Permission.ROOM_POLL_EARLY_RESULTS.value,
        Permission.ROOM_VIEWERS.value,
        Permission.ROOM_INVITE_ANONYMOUS.value,
    ],
    "__anonymous_event": [
        Permission.EVENT_VIEW.value,
    ],
    "__anonymous_room": [
        Permission.ROOM_QUESTION_READ.value,
        Permission.ROOM_QUESTION_ASK.value,
        Permission.ROOM_QUESTION_VOTE.value,
        Permission.ROOM_POLL_READ.value,
        Permission.ROOM_POLL_VOTE.value,
        Permission.ROOM_VIEW.value,
    ],
}
