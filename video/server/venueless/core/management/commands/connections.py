import fnmatch

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand

from venueless.core.services.connections import get_connections
from venueless.live.channels import GROUP_VERSION


class Command(BaseCommand):
    help = "Manage connections"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(
            title="subcommands", dest="subcommand", required=True
        )

        subparsers.add_parser("list")
        c_drop = subparsers.add_parser("drop")
        c_drop.add_argument("label", nargs="*", type=str)
        c_reload = subparsers.add_parser("force_reload")
        c_reload.add_argument("label", nargs="*", type=str)

    def handle(self, *args, **options):
        if options["subcommand"] == "list":
            self._list(*args, **options)
        elif options["subcommand"] == "drop":
            self._drop(*args, **options)
        elif options["subcommand"] == "force_reload":
            self._force_reload(*args, **options)

    def _list(self, *args, **options):
        rc = async_to_sync(get_connections)()
        print("{:60} {}".format("label", "est. number of connections"))
        for k, v in rc.items():
            print("{:60} {}".format(k, v))

    def _drop(self, *args, **options):
        rc = async_to_sync(get_connections)()
        filters = options["label"] or ("*",)

        conns = []
        for k in rc.keys():
            for l in filters:
                if fnmatch.fnmatch(k, l):
                    conns.append(k)

        for c in conns:
            async_to_sync(get_channel_layer().group_send)(
                GROUP_VERSION.format(label=c), {"type": "connection.drop"}
            )

    def _force_reload(self, *args, **options):
        rc = async_to_sync(get_connections)()
        filters = options["label"] or ("*",)

        conns = []
        for k in rc.keys():
            for l in filters:
                if fnmatch.fnmatch(k, l):
                    conns.append(k)

        for c in conns:
            async_to_sync(get_channel_layer().group_send)(
                GROUP_VERSION.format(label=c), {"type": "connection.reload"}
            )
