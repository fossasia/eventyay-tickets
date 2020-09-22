from enum import Enum


class Permission(Enum):
    WORLD_VIEW = "world:view"
    WORLD_UPDATE = "world:update"
    WORLD_ANNOUNCE = "world:announce"
    WORLD_SECRETS = "world:secrets"
    WORLD_API = "world:api"
    WORLD_GRAPHS = "world:graphs"
    WORLD_ROOMS_CREATE_STAGE = "world:rooms.create.stage"
    WORLD_ROOMS_CREATE_CHAT = "world:rooms.create.chat"
    WORLD_ROOMS_CREATE_BBB = "world:rooms.create.bbb"
    WORLD_ROOMS_CREATE_EXHIBITION = "world:rooms.create.exhibition"
    WORLD_USERS_LIST = "world:users.list"
    WORLD_USERS_MANAGE = "world:users.manage"
    WORLD_CHAT_DIRECT = "world:chat.direct"
    WORLD_EXHIBITION_CONTACT = "world:exhibition.contact"
    WORLD_CONNECTIONS_UNLIMITED = "world:connections.unlimited"
    ROOM_ANNOUNCE = "room:announce"
    ROOM_VIEW = "room:view"
    ROOM_UPDATE = "room:update"
    ROOM_DELETE = "room:delete"
    ROOM_CHAT_READ = "room:chat.read"
    ROOM_CHAT_JOIN = "room:chat.join"
    ROOM_CHAT_SEND = "room:chat.send"
    ROOM_INVITE = "room:invite"
    ROOM_CHAT_MODERATE = "room:chat.moderate"
    ROOM_BBB_JOIN = "room:bbb.join"
    ROOM_BBB_MODERATE = "room:bbb.moderate"
    ROOM_BBB_RECORDINGS = "room:bbb.recordings"


MAX_PERMISSIONS_IF_SILENCED = {
    Permission.WORLD_VIEW,
    Permission.ROOM_VIEW,
    Permission.ROOM_CHAT_READ,
    Permission.ROOM_CHAT_JOIN,
}
