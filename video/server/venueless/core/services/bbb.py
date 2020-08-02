import hashlib
import logging
import random
from urllib.parse import urlencode, urljoin

import aiohttp
from channels.db import database_sync_to_async
from django.db import transaction
from django.db.models import Q
from lxml import etree
from yarl import URL

from venueless.core.models import BBBCall, BBBServer

logger = logging.getLogger(__name__)


def get_url(operation, params, base_url, secret):
    encoded = urlencode(params)
    payload = operation + encoded + secret
    checksum = hashlib.sha1(payload.encode()).hexdigest()
    return urljoin(
        base_url, "api/" + operation + "?" + encoded + "&checksum=" + checksum
    )


def choose_server(world, room=None, prefer_server=None):
    servers = BBBServer.objects.filter(active=True)
    if not room:
        servers = servers.filter(rooms_only=False)

    search_order = [
        servers.filter(Q(id=prefer_server) | Q(url=prefer_server)).filter(
            Q(world_exclusive=world) | Q(world_exclusive__isnull=True)
        ),
        servers.filter(world_exclusive=world),
        servers.filter(world_exclusive__isnull=True),
    ]
    for qs in search_order:
        servers = list(qs)
        if not servers:
            continue

        # TODO: Implement proper load balancing strategy
        return random.choice(servers)


@database_sync_to_async
@transaction.atomic
def get_create_params_for_call_id(call_id, record, user):
    try:
        call = BBBCall.objects.get(id=call_id, invited_members__in=[user])
        if not call.server.active:
            call.server = choose_server(world=call.world)
            call.save(update_fields=["server"])
    except BBBCall.DoesNotExist:
        return None, None

    create_params = {
        "name": "Call",
        "meetingID": call.meeting_id,
        "attendeePW": call.attendee_pw,
        "moderatorPW": call.moderator_pw,
        "record": "true" if record else "false",
        "meta_Source": "venueless",
        "meta_Call": str(call_id),
    }
    if call.voice_bridge:
        create_params["voiceBridge"] = call.voice_bridge
    if call.guest_policy:
        create_params["guestPolicy"] = call.guest_policy
    return create_params, call.server


@database_sync_to_async
@transaction.atomic
def get_create_params_for_room(
    room, record, voice_bridge, guest_policy, prefer_server=None
):
    try:
        call = BBBCall.objects.get(room=room)
        if not call.server.active:
            call.server = choose_server(world=room.world, room=room)
            call.save(update_fields=["server"])
    except BBBCall.DoesNotExist:
        call = BBBCall.objects.create(
            room=room,
            world=room.world,
            server=choose_server(
                world=room.world, room=room, prefer_server=prefer_server
            ),
            voice_bridge=voice_bridge,
            guest_policy=guest_policy,
        )

    create_params = {
        "name": room.name,
        "meetingID": call.meeting_id,
        "attendeePW": call.attendee_pw,
        "moderatorPW": call.moderator_pw,
        "record": "true" if record else "false",
        "meta_Source": "venueless",
        "meta_World": room.world_id,
        "meta_Room": str(room.id),
    }
    if call.voice_bridge:
        create_params["voiceBridge"] = call.voice_bridge
    if call.guest_policy:
        create_params["guestPolicy"] = call.guest_policy
    return create_params, call.server


class BBBService:
    def __init__(self, world_id):
        self.world_id = world_id

    async def _create(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(URL(url, encoded=True)) as resp:
                    if resp.status != 200:
                        logger.error(
                            f"Could not create BBB meeting. Return code: {resp.status}"
                        )
                        return False

                    body = await resp.text()

                root = etree.fromstring(body)
                if root.xpath("returncode")[0].text != "SUCCESS":
                    logger.error(f"Could not create BBB meeting. Response: {body}")
                    return False
        except:
            logger.exception("Could not create BBB meeting.")
            return False
        return True

    async def get_join_url_for_room(self, room, user, moderator=False):
        m = [m for m in room.module_config if m["type"] == "call.bigbluebutton"][0]
        config = m["config"]
        create_params, server = await get_create_params_for_room(
            room,
            record=config.get("record", False),
            voice_bridge=config.get("voice_bridge", None),
            prefer_server=config.get("prefer_server", None),
            guest_policy="ASK_MODERATOR"
            if config.get("waiting_room", False)
            else "ALWAYS_ACCEPT",
        )
        create_url = get_url("create", create_params, server.url, server.secret)
        if not await self._create(create_url):
            return

        return get_url(
            "join",
            {
                "meetingID": create_params["meetingID"],
                "fullName": user.profile.get("display_name", ""),
                "userID": str(user.pk),
                "password": create_params["moderatorPW"]
                if moderator
                else create_params["attendeePW"],
                "joinViaHtml5": "true",
                "guest": "true"
                if not moderator and config.get("waiting_room", False)
                else "false",
            },
            server.url,
            server.secret,
        )

    async def get_join_url_for_call_id(self, call_id, user):
        create_params, server = await get_create_params_for_call_id(
            call_id, False, user
        )
        if not create_params:
            return
        create_url = get_url("create", create_params, server.url, server.secret)
        if not await self._create(create_url):
            return

        return get_url(
            "join",
            {
                "meetingID": create_params["meetingID"],
                "fullName": user.profile.get("display_name", ""),
                "userID": str(user.pk),
                "password": create_params["moderatorPW"],
                "joinViaHtml5": "true",
            },
            server.url,
            server.secret,
        )
