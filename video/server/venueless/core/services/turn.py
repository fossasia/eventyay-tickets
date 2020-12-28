import logging
import random

from venueless.core.models import TurnServer

logger = logging.getLogger(__name__)


def choose_server(world):
    servers = TurnServer.objects.filter(active=True)
    search_order = [
        servers.filter(world_exclusive=world),
        servers.filter(world_exclusive__isnull=True),
    ]
    for qs in search_order:
        servers = list(qs)
        if not servers:
            continue

        # Servers are sorted by cost, let's do a random pick if we have multiple with the smallest cost
        server = random.choice(servers)
        return server
