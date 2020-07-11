import hashlib
import logging
import random
from urllib.parse import urlencode, urljoin

import aiohttp
from channels.db import database_sync_to_async
from django.db import transaction
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


def choose_server():
    all_servers = BBBServer.objects.filter(active=True)
    # TODO: Implement proper load balancing strategy
    return random.choice(all_servers)


@database_sync_to_async
@transaction.atomic
def get_create_params_for_call_id(call_id, record, user):
    try:
        call = BBBCall.objects.get(id=call_id, invited_members__in=[user])
        if not call.server.active:
            call.server = choose_server()
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
    return create_params, call.server


@database_sync_to_async
@transaction.atomic
def get_create_params_for_room(room, record):
    try:
        call = BBBCall.objects.get(room=room)
        if not call.server.active:
            call.server = choose_server()
            call.save(update_fields=["server"])
    except BBBCall.DoesNotExist:
        call = BBBCall.objects.create(
            room=room, world=room.world, server=choose_server()
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
            room, record=config.get("record", False)
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
