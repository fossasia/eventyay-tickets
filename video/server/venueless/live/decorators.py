import functools

from venueless.core.permissions import Permission
from venueless.core.services.world import get_room
from venueless.live.exceptions import ConsumerException


def command(event_name):
    """
    Registers a function to be the handler of a specific command within a module.
    """

    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(self, *args):
            return await func(self, *args)

        wrapped._command = event_name
        return wrapped

    return wrapper


def event(event_name, refresh_world=False, refresh_user=False):
    """
    Registers a function to be the handler of a specific event within a module.
    """

    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(self, *args):
            if refresh_world:
                await self.consumer.world.refresh_from_db_if_outdated()
            if refresh_user:
                await self.consumer.user.refresh_from_db_if_outdated()
            return await func(self, *args)

        wrapped._event = event_name
        return wrapped

    return wrapper


def room_action(permission_required: Permission = None, module_required=None):
    """
    Wraps a command on a live module. Requires either ``room`` or ``channel`` to be set in the request body.

    :param permission_required: If set, the decorator will return an error if the user is not logged in or does not
                                have the specified permission.
    :param module_required: If set, the decorator will return an error if the room does not contain a module of the
                            given type. If a module is found, ``self.module_config`` will be set.
    :return:
    """

    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(self, body, *args):
            if "room" in body:
                self.room = self.consumer.room_cache.get(("room", body["room"]))
                if self.room:
                    await self.room.refresh_from_db_if_outdated()
                else:
                    self.room = await get_room(
                        world=self.consumer.world, id=body["room"]
                    )
                    self.consumer.room_cache["room", body["room"]] = self.room
            elif "channel" in body:
                self.room = self.consumer.room_cache.get(("channel", body["channel"]))
                if self.room:
                    await self.room.refresh_from_db_if_outdated()
                else:
                    self.room = await get_room(
                        world=self.consumer.world, channel__id=body["channel"]
                    )
                    self.consumer.room_cache["channel", body["channel"]] = self.room
            else:
                raise ConsumerException("room.unknown", "Unknown room ID")
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
                if not await self.consumer.world.has_permission_async(
                    user=self.consumer.user,
                    permission=permission_required,
                    room=self.room,
                ):
                    raise ConsumerException("protocol.denied", "Permission denied.")
            try:
                return await func(self, body, *args)
            finally:
                del self.room

        return wrapped

    return wrapper


def require_world_permission(permission: Permission):
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(self, *args):
            if not getattr(self.consumer, "user", None):  # pragma: no cover
                # Just a precaution, should never be called since MainConsumer.receive_json already checks this
                raise ConsumerException(
                    "protocol.unauthenticated", "No authentication provided."
                )
            if not await self.consumer.world.has_permission_async(
                user=self.consumer.user, permission=permission
            ):
                raise ConsumerException("auth.denied", "Permission denied.")
            return await func(self, *args)

        return wrapped

    return wrapper
