import logging

from venueless.core.models.question import Question
from venueless.core.permissions import Permission
from venueless.core.services.question import (
    create_question,
    delete_question,
    get_question,
    get_questions,
    pin_question,
    unpin_question,
    update_question,
    vote_on_question,
)
from venueless.live.channels import (
    GROUP_ROOM_QUESTION_MODERATE,
    GROUP_ROOM_QUESTION_READ,
)
from venueless.live.decorators import command, event, room_action
from venueless.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class QuestionModule(BaseModule):
    prefix = "question"

    @command("ask")
    @room_action(
        permission_required=Permission.ROOM_QUESTION_ASK, module_required="question"
    )
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
                "type": "question.created_or_updated",
                "room": str(self.room.pk),
                "question": question,
            },
        )

    @command("update")
    @room_action(
        permission_required=Permission.ROOM_QUESTION_MODERATE,
        module_required="question",
    )
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
                "type": "question.created_or_updated",
                "room": str(self.room.pk),
                "question": new_question,
            },
        )

    @command("delete")
    @room_action(
        permission_required=Permission.ROOM_QUESTION_MODERATE,
        module_required="question",
    )
    async def delete_question(self, body):
        if not self.module_config.get("active", False):
            await self.consumer.send_error("question.inactive")
            return
        old_question = await get_question(body.get("id"), self.room)
        await delete_question(**body)
        await self.consumer.send_success({"question": old_question["id"]})
        group = (
            GROUP_ROOM_QUESTION_MODERATE
            if old_question["state"] != Question.States.VISIBLE
            else GROUP_ROOM_QUESTION_READ
        )
        await self.consumer.channel_layer.group_send(
            group.format(id=self.room.pk),
            {
                "type": "question.deleted",
                "room": str(self.room.pk),
                "id": old_question["id"],
            },
        )

    @command("vote")
    @room_action(
        permission_required=Permission.ROOM_QUESTION_VOTE, module_required="question"
    )
    async def vote(self, body):
        if not self.module_config.get("active", False):
            await self.consumer.send_error("question.inactive")
            return

        try:
            question = await vote_on_question(
                room=body.get("room"),
                pk=body.get("id"),
                user=self.consumer.user,
                vote=body.get("vote", True),
            )
        except Exception as e:
            await self.consumer.send_error("question.vote", message=str(e))
            return

        await self.consumer.send_success({"question": question})

        group = (
            GROUP_ROOM_QUESTION_MODERATE
            if question["state"] != Question.States.VISIBLE
            else GROUP_ROOM_QUESTION_READ
        )
        await self.consumer.channel_layer.group_send(
            group.format(id=self.room.pk),
            {
                "type": "question.created_or_updated",
                "room": str(self.room.pk),
                "question": question,
            },
        )

    @command("list")
    @room_action(permission_required=Permission.ROOM_QUESTION_READ)
    async def list_questions(self, body):
        questions = []
        if await self.consumer.world.has_permission_async(
            user=self.consumer.user,
            room=self.room,
            permission=Permission.ROOM_QUESTION_MODERATE,
        ):
            questions = await get_questions(
                room=self.room.id, for_user=self.consumer.user
            )
        else:
            questions = await get_questions(
                room=self.room.id,
                state=Question.States.VISIBLE,
                add_by_user=self.consumer.user,
                for_user=self.consumer.user,
            )
        await self.consumer.send_success(questions)

    @command("pin")
    @room_action(permission_required=Permission.ROOM_QUESTION_MODERATE)
    async def pin_question(self, body):
        question = await get_question(body.get("id"), self.room)
        await pin_question(pk=question["id"], room=self.room)
        await self.consumer.send_success({"id": str(question["id"])})
        group = (
            GROUP_ROOM_QUESTION_MODERATE
            if question["state"] != Question.States.VISIBLE
            else GROUP_ROOM_QUESTION_READ
        )
        await self.consumer.channel_layer.group_send(
            group.format(id=self.room.pk),
            {
                "type": "question.pinned",
                "room": str(self.room.pk),
                "id": question["id"],
            },
        )

    @command("unpin")
    @room_action(permission_required=Permission.ROOM_QUESTION_MODERATE)
    async def unpin_question(self, body):
        await unpin_question(room=self.room)
        await self.consumer.send_success()
        group = GROUP_ROOM_QUESTION_READ
        await self.consumer.channel_layer.group_send(
            group.format(id=self.room.pk),
            {
                "type": "question.unpinned",
                "room": str(self.room.pk),
            },
        )

    @event("created_or_updated")
    async def push_question(self, body):
        await self.consumer.send_json(
            ["question.created_or_updated", {"question": body.get("question")}]
        )

    @event("deleted")
    async def push_delete(self, body):
        await self.consumer.send_json(
            [
                "question.deleted",
                {"room": body.get("room"), "id": body.get("id")},
            ]
        )

    @event("pinned")
    async def push_pin(self, body):
        await self.consumer.send_json(
            [
                "question.pinned",
                {"room": body.get("room"), "id": body.get("id")},
            ]
        )

    @event("unpinned")
    async def push_unpin(self, body):
        await self.consumer.send_json(
            [
                "question.unpinned",
                {"room": body.get("room")},
            ]
        )
