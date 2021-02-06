import hashlib
import json
import logging
import random

import websockets
from django.utils.crypto import get_random_string

from venueless.core.models import JanusServer

logger = logging.getLogger(__name__)


class JanusError(Exception):
    pass


class JanusPluginError(JanusError):
    pass


def choose_server(world):
    servers = JanusServer.objects.filter(active=True)
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


async def room_exists(server, roomid):
    # todo: handle connection errors to janus, encapsulate room creation into service
    async with websockets.connect(
        server.url, subprotocols=["janus-protocol"]
    ) as websocket:
        await websocket.send(
            json.dumps({"janus": "create", "transaction": get_random_string()})
        )
        resp = json.loads(await websocket.recv())
        session_id = resp["data"]["id"]

        await websocket.send(
            json.dumps(
                {
                    "janus": "attach",
                    "plugin": "janus.plugin.videoroom",
                    "transaction": get_random_string(),
                    "session_id": session_id,
                }
            )
        )
        resp = json.loads(await websocket.recv())
        if resp["janus"] != "success":
            raise JanusError(repr(resp))

        handle_id = resp["data"]["id"]

        await websocket.send(
            json.dumps(
                {
                    # Docs: https://janus.conf.meetecho.com/docs/videoroom.html
                    "janus": "message",
                    "body": {
                        "request": "exists",
                        "room": roomid,
                    },
                    "transaction": get_random_string(),
                    "session_id": session_id,
                    "handle_id": handle_id,
                }
            )
        )
        resp = json.loads(await websocket.recv())

        if resp["janus"] != "success":
            raise JanusError(repr(resp))
        if "error" in resp["plugindata"]["data"]:
            raise JanusPluginError(resp["plugindata"]["data"]["error"])

        return resp["plugindata"]["data"]["exists"]


async def create_room(server, bitrate=200_000):
    token = get_random_string(16)
    seed = get_random_string(16)
    # todo: handle connection errors to janus, encapsulate room creation into service
    async with websockets.connect(
        server.url, subprotocols=["janus-protocol"]
    ) as websocket:
        await websocket.send(
            json.dumps({"janus": "create", "transaction": get_random_string()})
        )
        resp = json.loads(await websocket.recv())
        session_id = resp["data"]["id"]

        await websocket.send(
            json.dumps(
                {
                    "janus": "attach",
                    "plugin": "janus.plugin.videoroom",
                    "transaction": get_random_string(),
                    "session_id": session_id,
                }
            )
        )
        resp = json.loads(await websocket.recv())
        if resp["janus"] != "success":
            raise JanusError(repr(resp))

        handle_id = resp["data"]["id"]

        await websocket.send(
            json.dumps(
                {
                    # Docs: https://janus.conf.meetecho.com/docs/videoroom.html
                    "janus": "message",
                    "body": {
                        "request": "create",
                        "admin_key": server.room_create_key,
                        "permanent": False,
                        "secret": hashlib.sha256(
                            f"{server.room_create_key}:secret:{seed}".encode()
                        ).hexdigest(),
                        "is_private": True,
                        "require_pvtid": True,
                        "lock_record": True,
                        "notify_joining": True,
                        "publishers": 100,  # todo
                        "allowed": [token],
                        "bitrate": bitrate,
                    },
                    "transaction": get_random_string(),
                    "session_id": session_id,
                    "handle_id": handle_id,
                }
            )
        )
        resp = json.loads(await websocket.recv())

        if resp["janus"] != "success":
            raise JanusError(repr(resp))
        if "error" in resp["plugindata"]["data"]:
            raise JanusPluginError(resp["plugindata"]["data"]["error"])

        room_id = resp["plugindata"]["data"]["room"]

    return {
        "server": server.url,
        "roomId": room_id,
        "token": token,
        "seed": seed,
    }
