import logging
from functools import cached_property

from venueless.core.models.question import Question
from venueless.core.permissions import Permission
from venueless.core.services.question import (
    create_question,
    get_question,
    update_question,
)
from venueless.live.channels import (
    GROUP_ROOM_QUESTION_MODERATE,
    GROUP_ROOM_QUESTION_READ,
)
from venueless.live.decorators import (
    command,
    event,
    room_action,
)
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class QuestionModule(BaseModule):
    prefix = "question"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @cached_property
    def module_config(self):
        module = [m for m in self.room.module_config if m.get("type", "") == "question"]
        if module:
            return module[0].get("config", {})
        return {}

    @command("ask")
    @room_action(permission_required=Permission.ROOM_QUESTION_ASK)
    async def ask_question(self, body):
        if not self.module_config.get("active", False):
            await self.consumer.send_error("question.inactive")
            return

        requires_moderation = self.module_config.get("requires_moderation", True)
        question = await create_question(
            content=body.get("content"),
            sender=self.consumer.user,
            room=self.room,
            state=Question.States.MOD_QUEUE
            if requires_moderation
            else Question.States.VISIBLE,
        )

        await self.consumer.send_success({"question": question})
        group = (
            GROUP_ROOM_QUESTION_MODERATE
            if requires_moderation
            else GROUP_ROOM_QUESTION_READ
        )
        await self.consumer.channel_layer.group_send(
            group.format(id=self.room.pk),
            {
                "type": "question.question",
                "room": str(self.room.pk),
                "question": question,
            },
        )

    @command("update")
    @room_action(permission_required=Permission.ROOM_QUESTION_MODERATE)
    async def update_question(self, body):
        if not self.module_config.get("active", False):
            await self.consumer.send_error("question.inactive")
            return

        old_question = await get_question(body.get("id"), self.room)
        body["room"] = self.room
        new_question = await update_question(
            moderator=self.consumer.user,
            **body,
        )

        await self.consumer.send_success({"question": new_question})

        group = (
            GROUP_ROOM_QUESTION_MODERATE
            if old_question["state"] != Question.States.VISIBLE
            and new_question["state"] != Question.States.VISIBLE
            else GROUP_ROOM_QUESTION_READ
        )
        await self.consumer.channel_layer.group_send(
            group.format(id=self.room.pk),
            {
                "type": "question.question",
                "room": str(self.room.pk),
                "question": new_question,
            },
        )

    @event("question")
    async def push_question(self, body):
        await self.consumer.send_json(
            ["question.question", {"question": body.get("question")}]
        )
