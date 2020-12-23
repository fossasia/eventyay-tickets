import logging

from venueless.live.exceptions import ConsumerException

logger = logging.getLogger(__name__)


class BaseModuleMeta(type):
    def __new__(cls, clsname, bases, attrs):
        newclass = super().__new__(cls, clsname, bases, attrs)
        newclass._commands = {}
        newclass._events = {}
        for key, val in attrs.items():
            event = getattr(val, "_event", None)
            if event is not None:
                newclass._events[event] = val
            command = getattr(val, "_command", None)
            if command is not None:
                newclass._commands[command] = val
        return newclass


class BaseModule(metaclass=BaseModuleMeta):
    prefix = None

    def __init__(self, consumer):
        self.consumer = consumer

    async def dispatch_event(self, content):
        event_type = content["type"].split(".")[1]
        if event_type in self._events:
            await self._events[event_type](self, content)
        else:  # pragma: no cover
            logger.warning(
                f'Ignored unknown event {content["type"]}'
            )  # ignore unknown event

    async def dispatch_command(self, content):
        action = content[0].split(".", 1)[1]
        if action not in self._commands:
            raise ConsumerException(f"{self.prefix}.unsupported_command")
        await self._commands[action](self, content[2])
