import collections
import fnmatch
import time

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.management.base import BaseCommand
from tqdm import tqdm

from venueless.core.services.connections import get_connections
from venueless.core.utils.redis import aioredis
from venueless.live.channels import GROUP_VERSION


class Command(BaseCommand):
    help = "Manage connections"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(
            title="subcommands", dest="subcommand", required=True
        )

        subparsers.add_parser("list")

        c = subparsers.add_parser("drop")
        c.add_argument(
            "filter",
            nargs="*",
            type=str,
            help='Filter for connection labels, e.g. "ff350b4.production" or "ff350b4.*" or '
            '"*.production". Defaults to "*".',
        )
        c.add_argument(
            "--interval",
            dest="interval",
            type=int,
            default=0,
            help="Interval for staggered execution. If set to a value different then zero, we will "
            "wait this many milliseconds between every client we send the message to.",
        )

        c = subparsers.add_parser("force_reload")
        c.add_argument(
            "filter",
            nargs="*",
            type=str,
            help='Filter for connection labels, e.g. "ff350b4.production" or "ff350b4.*" or '
            '"*.production". Defaults to "*".',
        )
        c.add_argument(
            "--interval",
            dest="interval",
            type=int,
            default=0,
            help="Interval for staggered execution. If set to a value different then zero, we will "
            "wait this many milliseconds between every client we send the message to.",
        )

    def handle(self, *args, **options):
        if options["subcommand"] == "list":
            self._list(*args, **options)
        elif options["subcommand"] == "drop":
            self._drop(*args, **options)
        elif options["subcommand"] == "force_reload":
            self._force_reload(*args, **options)

    def _list(self, *args, **options):
        rc = async_to_sync(get_connections)()
        print("{:60} {}".format("filter", "est. number of connections"))
        for k, v in rc.items():
            print("{:60} {}".format(k, v))

    def _drop(self, *args, **options):
        rc = async_to_sync(get_connections)()
        filters = options["filter"] or ("*",)

        conns = []
        for key in rc.keys():
            for fil in filters:
                if fnmatch.fnmatch(key, fil):
                    conns.append(key)

        self._staggered_group_send(
            conns,
            {"type": "connection.drop"},
            interval=options["interval"],
        )

    def _force_reload(self, *args, **options):
        rc = async_to_sync(get_connections)()
        filters = options["filter"] or ("*",)

        conns = []
        for key in rc.keys():
            for fil in filters:
                if fnmatch.fnmatch(key, fil):
                    conns.append(key)

        self._staggered_group_send(
            conns,
            {"type": "connection.reload"},
            interval=options["interval"],
        )

    def _group_messages(self, channel_names, message):
        cl = get_channel_layer()
        # Connection dict keyed by index to list of redis keys mapped on that index
        connection_to_channel_keys = collections.defaultdict(list)

        # For each channel
        for channel in channel_names:
            channel_non_local_name = channel
            if "!" in channel:
                channel_non_local_name = cl.non_local_name(channel)
            # Get its redis key
            channel_key = cl.prefix + channel_non_local_name
            message = dict(message.items())
            message["__asgi_channel__"] = [channel]
            idx = cl.consistent_hash(channel_non_local_name)
            connection_to_channel_keys[idx].append((channel_key, cl.serialize(message)))

        return (connection_to_channel_keys,)

    @async_to_sync
    async def _staggered_group_send(self, conns, message, interval):
        """
        Sends a message to the entire group, but wait for `interval` between every message.
        Capacity is ignored -- we want these management commands to reach the client even if they get a lot of
        spam.
        """
        cl = get_channel_layer()
        groups = [GROUP_VERSION.format(label=c) for c in conns]
        if interval == 0:
            for group in groups:
                await cl.group_send(group, message)
            return

        if settings.REDIS_USE_PUBSUB:
            channel_names = []

            async with aioredis() as redis:
                for v in conns:
                    await redis.zremrangebyscore(
                        f"version.{v}", min=0, max=int(time.time()) - 24 * 3600
                    )
                    channel_names += [
                        x.decode("utf8")
                        for x in await redis.zrange(f"version.{v}", 0, -1)
                    ]

            for name in tqdm(channel_names):
                await cl.send(name, message)
                time.sleep(float(interval) / 1000.0)
        else:
            channel_names = []
            for group in groups:
                assert cl.valid_group_name(group), "Group name not valid"
                # Retrieve list of all channel names
                key = cl._group_key(group)
                async with cl.connection(cl.consistent_hash(group)) as connection:
                    # Discard old channels based on group_expiry
                    await connection.zremrangebyscore(
                        key, min=0, max=int(time.time()) - cl.group_expiry
                    )

                    channel_names += [
                        x.decode("utf8") for x in await connection.zrange(key, 0, -1)
                    ]

            (connection_to_channel_keys,) = self._group_messages(channel_names, message)
            with tqdm(total=len(channel_names)) as pbar:
                for (
                    connection_index,
                    channel_redis_keys,
                ) in connection_to_channel_keys.items():
                    async with cl.connection(connection_index) as connection:
                        for key, message in channel_redis_keys:
                            await connection.zadd(key, int(time.time()), message)
                            await connection.expire(key, cl.expiry)
                            time.sleep(float(interval) / 1000.0)
                            pbar.update(1)
