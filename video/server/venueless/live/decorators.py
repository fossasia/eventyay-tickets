import functools

from venueless.core.permissions import Permission
from venueless.core.services.world import get_room
from venueless.live.exceptions import ConsumerException


def room_action(permission_required: Permission = None, module_required=None):
    """
    Wraps an action on a live module. Requires either ``self.room_id`` or ``self.channel_id`` to be set by the dispatch
    method. Sets ``self.room`` with the room object.

    :param permission_required: If set, the decorator will return an error if the user is not logged in or does not
                                have the specified permission.
    :param module_required: If set, the decorator will return an error if the room does not contain a module of the
                            given type. If a module is found, ``self.module_config`` will be set.
    :return:
    """

    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(self, *args):
            if hasattr(self, "room_id"):
                self.room = await get_room(world=self.world, id=self.room_id)
            elif hasattr(self, "channel_id"):
                self.room = await get_room(
                    world=self.world, channel__id=self.channel_id
                )
            if not self.room:
                raise ConsumerException("room.unknown", "Unknown room ID")

            if module_required is not None:
                module_config = [
                    m["config"]
                    for m in self.room.module_config
                    if m["type"] == module_required
                ]
                if module_config:
                    self.module_config = module_config[0]
                else:
                    raise ConsumerException(
                        "room.unknown", "Room does not contain a matching module."
                    )

            if permission_required is not None:
                if not getattr(self.consumer, "user", None):  # pragma: no cover
                    # Just a precaution, should never be called since MainConsumer.receive_json already checks this
                    raise ConsumerException(
                        "protocol.unauthenticated", "No authentication provided."
                    )
                if not await self.world.has_permission_async(
                    user=self.consumer.user,
                    permission=permission_required,
                    room=self.room,
                ):
                    raise ConsumerException("protocol.denied", "Permission denied.")
            try:
                return await func(self, *args)
            finally:
                del self.room

        return wrapped

    return wrapper


def require_world_permission(permission: Permission):
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(self, *args):
            if not getattr(self.consumer, "user", None):
                raise ConsumerException(
                    "bbb.unknown", "Room does not contain a BBB room."
                )
            if not await self.world.has_permission_async(
                user=self.consumer.user, permission=permission
            ):
                raise ConsumerException("auth.denied", "Permission denied.")
            return await func(self, *args)

        return wrapped

    return wrapper
