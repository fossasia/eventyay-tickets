import hashlib
import logging
from urllib.parse import urlencode, urljoin

import aiohttp
from lxml import etree
from yarl import URL

logger = logging.getLogger(__name__)


def derive_meeting_id(world_id, room_id, secret):
    return hashlib.sha256(
        f"{secret}:world:{world_id}:room:{room_id}".encode()
    ).hexdigest()[:16]


def derive_attendee_pw(world_id, room_id, secret):
    return hashlib.sha256(
        f"{secret}:world:{world_id}:room:{room_id}:attendee_pw".encode()
    ).hexdigest()[:16]


def derive_moderator_pw(world_id, room_id, secret):
    return hashlib.sha256(
        f"{secret}:world:{world_id}:room:{room_id}:moderator_pw".encode()
    ).hexdigest()[:16]


def get_url(operation, params, base_url, secret):
    encoded = urlencode(params)
    payload = operation + encoded + secret
    checksum = hashlib.sha1(payload.encode()).hexdigest()
    return urljoin(
        base_url, "api/" + operation + "?" + encoded + "&checksum=" + checksum
    )


def get_create_params(room):
    m = [m for m in room.module_config if m["type"] == "call.bigbluebutton"][0]
    config = m["config"]
    create_params = {
        "name": room.name,
        "meetingID": derive_meeting_id(room.world_id, str(room.id), config["secret"]),
        "attendeePW": derive_attendee_pw(room.world_id, str(room.id), config["secret"]),
        "moderatorPW": derive_moderator_pw(
            room.world_id, str(room.id), config["secret"]
        ),
        "record": "true" if config.get("record", False) else "false",
        "meta_Source": "venueless",
        "meta_World": room.world_id,
        "meta_Room": str(room.id),
    }
    return create_params


class BBBService:
    def __init__(self, world_id):
        self.world_id = world_id

    async def get_join_url(self, room, uid, display_name, moderator=False):
        m = [m for m in room.module_config if m["type"] == "call.bigbluebutton"][0]
        config = m["config"]
        create_params = get_create_params(room)
        create_url = get_url("create", create_params, config["url"], config["secret"])

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(URL(create_url, encoded=True)) as resp:
                    if resp.status != 200:
                        logger.error(
                            f"Could not create BBB meeting. Return code: {resp.status}"
                        )
                        return

                    body = await resp.text()

                root = etree.fromstring(body)
                if root.xpath("returncode")[0].text != "SUCCESS":
                    logger.error(f"Could not create BBB meeting. Response: {body}")
                    return
        except:
            logger.exception("Could not create BBB meeting.")
            return

        return get_url(
            "join",
            {
                "meetingID": create_params["meetingID"],
                "fullName": display_name,
                "userID": uid,
                "password": create_params["moderatorPW"]
                if moderator
                else create_params["attendeePW"],
                "joinViaHtml5": "true",
            },
            config["url"],
            config["secret"],
        )
