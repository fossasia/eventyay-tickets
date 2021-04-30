import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from django.conf import settings

logger = logging.getLogger(__name__)

_state = threading.local()


class StatsdProtocol(asyncio.DatagramProtocol):
    def __init__(self, prefix):
        self.transport = None
        self.prefix = prefix

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        self.transport = False

    def send(self, data):
        try:
            for stat in data.keys():
                value = data[stat]
                send_data = "%s.%s:%s" % (self.prefix, stat, value)
                self.transport.sendto(send_data.encode("utf-8"))
        except Exception as e:
            logger.error("Statsd error %r", e)


class StatsD:
    def __init__(self, loop, host, port, prefix):
        self.loop = loop
        self.host = host
        self.port = port

        self.prefix = "apps.%s" % prefix
        self.protocol = None

    async def start(self):
        logger.debug(f"StatsD connection to {self.host}:{self.port} established")
        _, self.protocol = await self.loop.create_datagram_endpoint(
            lambda: StatsdProtocol(self.prefix), remote_addr=(self.host, self.port)
        )

    def stop(self):
        if self.protocol:
            self.protocol.transport.close()

    def timing(self, stats, time):
        self._update(stats, time, "ms")

    def increment(self, stats):
        self._update(stats, 1)

    def decrement(self, stats):
        self._update(stats, -1)

    def gauge(self, stats, value):
        self._update(stats, value, "g")

    def _update(self, stats, delta=1, metric="c"):
        if type(stats) is not list:
            stats = [stats]
        data = {}
        for stat in stats:
            stat += f",env={settings.VENUELESS_ENVIRONMENT}"
            data[stat] = "%s|%s" % (delta, metric)
        self.protocol.send(data)


class FakeStatsD:
    def __init__(self):
        pass

    async def start(self):
        logger.debug("StatsD not configured")

    def stop(self):
        pass

    def timing(self, stats, time):
        pass

    def increment(self, stats):
        pass

    def decrement(self, stats):
        pass

    def gauge(self, stats, value):
        pass


@asynccontextmanager
async def statsd():
    if not hasattr(_state, "client"):
        if settings.STATSD_HOST:
            _state.client = StatsD(
                asyncio.get_event_loop(),
                settings.STATSD_HOST,
                int(settings.STATSD_PORT),
                "venueless",
            )
            await _state.client.start()
        else:
            _state.client = FakeStatsD()
    yield _state.client
