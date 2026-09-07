import re

from django.core import signing
from django.urls import reverse

from eventyay.core.permissions import Permission
from eventyay.features.live.decorators import command, room_action
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.base import BaseModule


class ZoomModule(BaseModule):
    prefix = "zoom"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @command("room_url")
    @room_action(
        permission_required=Permission.ROOM_ZOOM_JOIN,
        module_required="call.zoom",
    )
    async def room_url(self, body):
        if not self.consumer.user.profile.get("display_name"):
            raise ConsumerException("bbb.join.missing_profile")

        raw_meeting = (self.module_config.get("meeting_number") or "").strip()
        if not raw_meeting:
            raise ConsumerException("zoom.no_meeting_id")

        # Parse meeting number and passcode defensively:
        # Support full Zoom invite URLs, web client URLs, or plain numeric meeting IDs
        meeting_number = ""
        password = (self.module_config.get("password") or "").strip()

        if "zoom.us" in raw_meeting or "/" in raw_meeting:
            # Pattern for URLs like: /j/1234567890 or /w/1234567890 or /wc/1234567890/join or /wc/join/1234567890
            match = re.search(r"/(?:j|w|wc|my)(?:/join)?/([0-9]+)", raw_meeting)
            if match:
                meeting_number = match.group(1)
            # Extract passcode from URL parameter if not explicitly configured
            if not password:
                pwd_match = re.search(r"[?&]pwd=([^&#]+)", raw_meeting)
                if pwd_match:
                    password = pwd_match.group(1)

        if not meeting_number:
            meeting_number = re.sub(r"[^0-9]", "", raw_meeting)

        if not meeting_number:
            raise ConsumerException("zoom.no_meeting_id")

        zoom_defaults = getattr(self.consumer.event, "zoom_defaults", None) or {}
        client_id = (
            self.module_config.get("client_id")
            or zoom_defaults.get("client_id")
            or ""
        )
        client_secret = (
            self.module_config.get("client_secret")
            or zoom_defaults.get("client_secret")
            or ""
        )

        data = signing.dumps(
            {
                "mn": int(meeting_number),
                "pw": password,
                "un": self.consumer.user.profile.get("display_name"),
                "ho": bool(False),
                "ui": str(self.consumer.user.pk),
                "dc": self.module_config.get("disable_chat", False),
                "event_id": str(self.consumer.event.id),
                "client_id": client_id,
                "client_secret": client_secret,
            }
        )
        domain = (getattr(self.consumer.event, "domain", None) or "").strip()
        meeting_path = reverse("zoom:meeting")
        if domain:
            url = f"//{domain}{meeting_path}?data={data}"
        else:
            url = f"{meeting_path}?data={data}"
        await self.consumer.send_success({"url": url})
