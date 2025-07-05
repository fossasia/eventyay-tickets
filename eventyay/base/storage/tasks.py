import re
from contextlib import suppress

import asgiref
import channels

from eventyay.celery_app import app
from eventyay.base.models import ChatEvent
from eventyay.base.services.chat import ChatService
from eventyay.core.tasks import WorldTask
from eventyay.features.live.channels import GROUP_CHAT
from eventyay.base.storage.external import fetch_preview_data


@app.task(base=WorldTask)
def retrieve_preview_information(world=None, event_id=None):
    event = ChatEvent.objects.filter(id=event_id).first()
    if not event:
        return

    match = re.search(r"(?P<url>https?://[^\s]+)", event.content.get("body"))
    if not match:  # Message has changed in the meantime?
        return
    url = match.group("url")

    if url.endswith(")"):  # This is common enough to special-case it, I think
        url = url[:-1]

    preview_card = None
    with suppress(Exception):  # If this fails, just move on
        preview_card = fetch_preview_data(url, world)

    if preview_card:
        event.content["preview_card"] = preview_card
        event.save()

        event_data = asgiref.sync.async_to_sync(ChatService(world).create_event)(
            channel=event.channel,
            event_type=event.event_type,
            content=event.content,
            sender=event.sender,
            replaces=event.id,
        )
        channel_layer = channels.layers.get_channel_layer()
        asgiref.sync.async_to_sync(channel_layer.group_send)(
            GROUP_CHAT.format(channel=event.channel_id),
            event_data,
        )
