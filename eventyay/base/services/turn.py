import logging
import random

from eventyay.base.models import TurnServer

logger = logging.getLogger(__name__)


def choose_server(event):
    servers = TurnServer.objects.filter(active=True)
    search_order = [
        servers.filter(event_exclusive=event),
        servers.filter(event_exclusive__isnull=True),
    ]
    for qs in search_order:
        servers = list(qs)
        if not servers:
            continue

        # Servers are sorted by cost, let's do a random pick if we have multiple with the smallest cost
        server = random.choice(servers)
        return server
