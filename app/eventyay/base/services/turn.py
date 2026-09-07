import logging
import random

from eventyay.base.models import TurnServer
from .video_server_routing import filter_servers_for_event

logger = logging.getLogger(__name__)


def choose_server(event):
    servers = TurnServer.objects.filter(active=True)
    search_order = filter_servers_for_event(servers, event)
    for qs in search_order:
        servers_list = list(qs)
        if not servers_list:
            continue

        # Servers are sorted by cost, let's do a random pick if we have multiple with the smallest cost
        server = random.choice(servers_list)
        return server
