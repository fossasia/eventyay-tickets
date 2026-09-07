import asyncio
import hashlib
import json
import logging
import random
from contextlib import asynccontextmanager

import websockets
from django.utils.crypto import get_random_string
from websockets.exceptions import WebSocketException

from eventyay.base.models import JanusServer
from .video_server_routing import filter_servers_for_event

logger = logging.getLogger(__name__)

JANUS_CONNECT_TIMEOUT = 10
JANUS_RESPONSE_TIMEOUT = 10


class JanusError(Exception):
    pass


class JanusConfigurationError(JanusError):
    pass


class JanusPluginError(JanusError):
    pass


def choose_server(event):
    servers = JanusServer.objects.filter(active=True)
    search_order = filter_servers_for_event(servers, event)
    for qs in search_order:
        servers_list = list(qs)
        if not servers_list:
            continue

        server = random.choice(servers_list)
        return server


@asynccontextmanager
async def _janus_websocket(server):
    if not server:
        raise JanusConfigurationError("No active Janus server configured")

    try:
        async with websockets.connect(
            server.url,
            subprotocols=["janus-protocol"],
            open_timeout=JANUS_CONNECT_TIMEOUT,
            close_timeout=5,
        ) as websocket:
            yield websocket
    except (TimeoutError, OSError, WebSocketException) as e:
        raise JanusError(f"Could not connect to Janus server {server.url}: {e}") from e


async def _recv_response(websocket, transaction):
    while True:
        try:
            raw_response = await websocket.recv()
            resp = json.loads(raw_response)
        except TimeoutError as e:
            raise JanusError("Timed out waiting for Janus response") from e
        except (json.JSONDecodeError, TypeError) as e:
            raise JanusError("Janus returned an invalid JSON response") from e

        janus_type = resp.get("janus")
        if janus_type in ("ack", "keepalive"):
            continue
        if resp.get("transaction") != transaction:
            continue
        if janus_type == "error":
            error = resp.get("error") or {}
            reason = error.get("reason") or repr(resp)
            raise JanusError(reason)
        return resp


async def _janus_request(websocket, payload, *, expect_plugin_data=False):
    payload = payload.copy()
    transaction = payload.setdefault("transaction", get_random_string(length=12))

    await websocket.send(json.dumps(payload))

    try:
        resp = await asyncio.wait_for(
            _recv_response(websocket, transaction), timeout=JANUS_RESPONSE_TIMEOUT
        )
    except TimeoutError as e:
        raise JanusError("Timed out waiting for Janus response") from e

    janus_type = resp.get("janus")
    if janus_type != "success" and not (expect_plugin_data and janus_type == "event"):
        raise JanusError(repr(resp))

    if expect_plugin_data:
        plugin_data = resp.get("plugindata", {}).get("data")
        if not isinstance(plugin_data, dict):
            raise JanusError(repr(resp))
        if "error" in plugin_data:
            raise JanusPluginError(plugin_data["error"])
    elif "data" not in resp:
        raise JanusError(repr(resp))

    return resp


async def videoroom_add_token_if_exists(server, room_data, token, audiobridge=False):
    async with _janus_websocket(server) as websocket:
        resp = await _janus_request(
            websocket,
            {
                "janus": "create",
            },
        )
        session_id = resp["data"]["id"]

        resp = await _janus_request(
            websocket,
            {
                "janus": "attach",
                "plugin": "janus.plugin.videoroom",
                "session_id": session_id,
            },
        )
        handle_id = resp["data"]["id"]

        resp = await _janus_request(
            websocket,
            {
                "janus": "message",
                "body": {
                    "request": "exists",
                    "room": room_data["roomId"],
                },
                "session_id": session_id,
                "handle_id": handle_id,
            },
            expect_plugin_data=True,
        )
        exists = resp["plugindata"]["data"]["exists"]

        if exists:
            await _janus_request(
                websocket,
                {
                    "janus": "message",
                    "body": {
                        "request": "allowed",
                        "secret": hashlib.sha256(
                            f"{server.room_create_key}:secret:{room_data['seed']}".encode()
                        ).hexdigest(),
                        "room": room_data["roomId"],
                        "action": "add",
                        "allowed": [token],
                    },
                    "session_id": session_id,
                    "handle_id": handle_id,
                },
                expect_plugin_data=True,
            )

            if audiobridge:
                resp = await _janus_request(
                    websocket,
                    {
                        "janus": "attach",
                        "plugin": "janus.plugin.audiobridge",
                        "session_id": session_id,
                    },
                )
                audio_handle_id = resp["data"]["id"]
                await _janus_request(
                    websocket,
                    {
                        "janus": "message",
                        "body": {
                            "request": "allowed",
                            "secret": hashlib.sha256(
                                f"{server.room_create_key}:secret:{room_data['seed']}".encode()
                            ).hexdigest(),
                            "room": room_data["roomId"],
                            "action": "add",
                            "allowed": [token],
                        },
                        "session_id": session_id,
                        "handle_id": audio_handle_id,
                    },
                    expect_plugin_data=True,
                )

        return exists


def videoroom_secret(server, room_data):
    return hashlib.sha256(
        f"{server.room_create_key}:secret:{room_data['seed']}".encode()
    ).hexdigest()


async def videoroom_moderate(server, room_data, feed_id, mid="0", **moderation):
    async with _janus_websocket(server) as websocket:
        resp = await _janus_request(
            websocket,
            {
                "janus": "create",
            },
        )
        session_id = resp["data"]["id"]

        resp = await _janus_request(
            websocket,
            {
                "janus": "attach",
                "plugin": "janus.plugin.videoroom",
                "session_id": session_id,
            },
        )
        handle_id = resp["data"]["id"]

        req_body = {
            "request": "moderate",
            "secret": videoroom_secret(server, room_data),
            "room": room_data["roomId"],
            "id": int(feed_id),
            "mid": str(moderation.pop("mid", mid)),
            **moderation,
        }

        await _janus_request(
            websocket,
            {
                "janus": "message",
                "body": req_body,
                "session_id": session_id,
                "handle_id": handle_id,
            },
            expect_plugin_data=True,
        )


async def videoroom_kick(server, room_data, feed_id):
    async with _janus_websocket(server) as websocket:
        resp = await _janus_request(
            websocket,
            {
                "janus": "create",
            },
        )
        session_id = resp["data"]["id"]

        resp = await _janus_request(
            websocket,
            {
                "janus": "attach",
                "plugin": "janus.plugin.videoroom",
                "session_id": session_id,
            },
        )
        handle_id = resp["data"]["id"]

        await _janus_request(
            websocket,
            {
                "janus": "message",
                "body": {
                    "request": "kick",
                    "secret": videoroom_secret(server, room_data),
                    "room": room_data["roomId"],
                    "id": int(feed_id),
                },
                "session_id": session_id,
                "handle_id": handle_id,
            },
            expect_plugin_data=True,
        )


async def create_videoroom(
    server, room_id, init_token, audiobridge=False, bitrate=1_500_000
):
    seed = get_random_string(16)
    async with _janus_websocket(server) as websocket:
        resp = await _janus_request(
            websocket,
            {
                "janus": "create",
            },
        )
        session_id = resp["data"]["id"]

        resp = await _janus_request(
            websocket,
            {
                "janus": "attach",
                "plugin": "janus.plugin.videoroom",
                "session_id": session_id,
            },
        )
        handle_id = resp["data"]["id"]

        resp = await _janus_request(
            websocket,
            {
                "janus": "message",
                "body": {
                    "request": "create",
                    "room": room_id,
                    "admin_key": server.room_create_key,
                    "permanent": False,
                    "secret": hashlib.sha256(
                        f"{server.room_create_key}:secret:{seed}".encode()
                    ).hexdigest(),
                    "is_private": True,
                    "require_pvtid": True,
                    "lock_record": True,
                    "notify_joining": True,
                    "publishers": 100,
                    "allowed": [init_token],
                    "bitrate": bitrate,
                },
                "session_id": session_id,
                "handle_id": handle_id,
            },
            expect_plugin_data=True,
        )

        room_id = resp["plugindata"]["data"]["room"]

        if audiobridge:
            resp = await _janus_request(
                websocket,
                {
                    "janus": "attach",
                    "plugin": "janus.plugin.audiobridge",
                    "session_id": session_id,
                },
            )
            handle_id = resp["data"]["id"]

            await _janus_request(
                websocket,
                {
                    "janus": "message",
                    "body": {
                        "request": "create",
                        "room": room_id,
                        "admin_key": server.room_create_key,
                        "permanent": False,
                        "secret": hashlib.sha256(
                            f"{server.room_create_key}:secret:{seed}".encode()
                        ).hexdigest(),
                        "audiolevel_ext": True,
                        "audiolevel_event": True,
                        "audio_active_packets": 50,
                        "audio_level_average": 50,
                        "is_private": True,
                        "allowed": [init_token],
                        "record": False,
                    },
                    "session_id": session_id,
                    "handle_id": handle_id,
                },
                expect_plugin_data=True,
            )

    return {
        "server": server.url,
        "roomId": room_id,
        "seed": seed,
        "audiobridge": audiobridge,
    }
