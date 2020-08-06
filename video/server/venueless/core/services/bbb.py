import hashlib
import logging
import random
from datetime import datetime
from urllib.parse import urlencode, urljoin

import aiohttp
import pytz
from channels.db import database_sync_to_async
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q, Value
from django.urls import reverse
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
    servers = BBBServer.objects.filter(active=True).order_by("cost")
    if not room:
        servers = servers.filter(rooms_only=False)

    search_order = [
        servers.filter(url=prefer_server).filter(
            Q(world_exclusive=world) | Q(world_exclusive__isnull=True)
        ),
        servers.filter(world_exclusive=world),
        servers.filter(world_exclusive__isnull=True),
    ]
    for qs in search_order:
        servers = list(qs)
        if not servers:
            continue

        # Servers are sorted by cost, let's do a random pick if we have multiple with the smallest cost
        smallest_cost = servers[0].cost
        server = random.choice([s for s in servers if s.cost == smallest_cost])

        if len(servers) > 1:
            # Usually, if there are multiple servers, a cron job should be set up to the bbb_update_cost management
            # command that calculates an actual cost function based on the server load (see there for a definition of
            # the cost function). However, if the cron job does not run (or does not run soon enough), this little
            # UPDATE statement will make sure we have a round-robin-like distribution among the servers by increasing
            # the cost value temporarily with every added meeting.
            BBBServer.objects.filter(pk=server.pk).update(cost=F("cost") + Value("10"))
        return server


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
def get_call_for_room(room):
    return BBBCall.objects.select_related("server").filter(room=room).first()


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
    def __init__(self, world):
        self.world = world

    async def _get(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(URL(url, encoded=True)) as resp:
                    if resp.status != 200:
                        logger.error(
                            f"Could not contact BBB. Return code: {resp.status}"
                        )
                        return False

                    body = await resp.text()

                root = etree.fromstring(body)
                if root.xpath("returncode")[0].text != "SUCCESS":
                    logger.error(f"Could not contact BBB. Response: {body}")
                    return False
        except:
            logger.exception("Could not contact BBB.")
            return False
        return root

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
        if await self._get(create_url) is False:
            return

        scheme = 'http://' if settings.DEBUG else 'https://'  # TODO: better determinator?
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
                "userdata-bbb_custom_style_url": scheme + self.world.domain + reverse('live:css.bbb'),
                "userdata-bbb_show_public_chat_on_login": "false",
                "userdata-bbb_mirror_own_webcam": "true",
                "userdata-bbb_skip_check_audio": "true",
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
        if await self._get(create_url) is False:
            return

        scheme = 'http://' if settings.DEBUG else 'https://'  # TODO: better determinator?
        return get_url(
            "join",
            {
                "meetingID": create_params["meetingID"],
                "fullName": user.profile.get("display_name", ""),
                "userID": str(user.pk),
                "password": create_params["moderatorPW"],
                "joinViaHtml5": "true",
                "userdata-bbb_custom_style_url": scheme + self.world.domain + reverse('live:css.bbb'),
                "userdata-bbb_show_public_chat_on_login": "false",
                "userdata-bbb_mirror_own_webcam": "true",
                "userdata-bbb_skip_check_audio": "true",
            },
            server.url,
            server.secret,
        )

    async def get_recordings_for_room(self, room):
        call = await get_call_for_room(room)
        recordings_url = get_url(
            "getRecordings",
            {"meetingID": call.meeting_id, "state": "any"},
            call.server.url,
            call.server.secret,
        )
        root = await self._get(recordings_url)
        if root is False:
            return []

        tz = pytz.timezone(self.world.timezone)
        recordings = []
        for rec in root.xpath("recordings/recording"):
            url = None
            for f in rec.xpath("playback/format"):
                if f.xpath("type")[0].text != "presentation":
                    continue
                url = f.xpath("url")[0].text
            recordings.append(
                {
                    "start": (
                        datetime.utcfromtimestamp(
                            int(rec.xpath("startTime")[0].text) / 1000
                        )
                    )
                    .astimezone(tz)
                    .isoformat(),
                    "end": (
                        datetime.utcfromtimestamp(
                            int(rec.xpath("endTime")[0].text) / 1000
                        )
                    )
                    .astimezone(tz)
                    .isoformat(),
                    "participants": rec.xpath("participants")[0].text,
                    "state": rec.xpath("state")[0].text,
                    "url": url,
                }
            )
        return recordings
