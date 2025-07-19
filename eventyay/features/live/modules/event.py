import logging

from asgiref.sync import sync_to_async
from celery.result import AsyncResult
from channels.db import database_sync_to_async

from eventyay.core.permissions import Permission
from eventyay.base.services.event import (
    _config_serializer,
    generate_tokens,
    get_audit_log,
    get_event_config_for_user,
    notify_schedule_change,
    notify_event_change,
    save_event,
)
from eventyay.features.analytics.graphs.tasks import (
    generate_attendee_list,
    generate_attendee_session_list,
    generate_chat_history,
    generate_poll_history,
    generate_question_history,
    generate_report,
    generate_room_views,
    generate_session_views,
    generate_views,
)
from eventyay.features.importers.tasks import conftool_update_schedule
from eventyay.features.live.decorators import command, event, require_event_permission
from eventyay.features.live.modules.base import BaseModule

logger = logging.getLogger(__name__)


class EventModule(BaseModule):
    prefix = "event"

    @event("update", refresh_user=True)
    async def push_event_update(self, body):
        self.consumer.room_cache.clear()
        await self.consumer.event.refresh_from_db_if_outdated(allowed_age=0)
        event_config = await database_sync_to_async(get_event_config_for_user)(
            self.consumer.event,
            self.consumer.user,
        )
        self.consumer.known_room_id_cache = {r["id"] for r in event_config["rooms"]}
        await self.consumer.send_json(["event.updated", event_config])

    @event("schedule.update", refresh_user=True)
    async def push_schedule_update(self, body):
        await self.consumer.event.refresh_from_db_if_outdated(allowed_age=0)
        await self.consumer.send_json(
            [
                "event.schedule.updated",
                self.consumer.event.config.get("pretalx", {}),
            ]
        )

    @event("user_count_change")
    async def push_user_count_change(self, body):
        if body["room"] not in self.consumer.known_room_id_cache:
            # no permission to see this room, ignore
            return
        await self.consumer.send_json(
            [
                "event.user_count_change",
                {
                    "room": body["room"],
                    "users": body["users"],
                },
            ]
        )

    @command("config.get")
    @require_event_permission(Permission.EVENT_UPDATE)
    async def config_get(self, body):
        await self.consumer.send_success(_config_serializer(self.consumer.event).data)

    @command("config.patch")
    @require_event_permission(Permission.EVENT_UPDATE)
    async def config_patch(self, body):
        old = _config_serializer(self.consumer.event).data
        s = _config_serializer(self.consumer.event, data=body, partial=True)
        if s.is_valid():
            config_fields = (
                "theme",
                "date_locale",
                "connection_limit",
                "bbb_defaults",
                "pretalx",
                "videoPlayer",
                "profile_fields",
                "track_room_views",
                "track_event_views",
                "track_exhibitor_views",
                "onsite_traits",
                "conftool_url",
                "conftool_password",
                "iframe_blockers",
                "social_logins",
            )
            model_fields = (
                "title",
                "locale",
                "timezone",
                "roles",
                "trait_grants",
            )
            update_fields = set()

            for f in model_fields:
                if f in body:
                    setattr(self.consumer.event, f, s.validated_data[f])
                    update_fields.add(f)

            for f in config_fields:
                if f in body:
                    if f == "pretalx":
                        pretalx_data = s.validated_data["pretalx"]
                        old_pretalx_data = self.consumer.event.config.get("pretalx", {})
                        if any(
                            (pretalx_data.get(key) or "")
                            != (old_pretalx_data.get(key) or "")
                            for key in ("domain", "url", "event")
                        ):
                            s.validated_data["pretalx"]["connected"] = False
                    self.consumer.event.config[f] = s.validated_data[f]
                    update_fields.add("config")

            await database_sync_to_async(self.consumer.event.save)(
                update_fields=list(update_fields)
            )
            new = await save_event(
                self.consumer.event,
                list(update_fields),
                by_user=self.consumer.user,
                old_data=old,
            )
            await self.consumer.send_success(new)
            await notify_event_change(self.consumer.event.id)

            if "conftool_url" in body:
                await sync_to_async(conftool_update_schedule.apply_async)(
                    kwargs={"event": str(self.consumer.event.id)}
                )
            if old["pretalx"] != new["pretalx"]:
                await notify_schedule_change(event_id=self.consumer.event.id)
        else:
            await self.consumer.send_error(
                code="config.invalid",
                details=s.errors,
            )

    @command("tokens.generate")
    @require_event_permission(Permission.EVENT_UPDATE)
    async def tokens_generate(self, body):
        result = await generate_tokens(
            self.consumer.event,
            body["number"],
            body["traits"],
            body["days"],
            by_user=self.consumer.user,
            long=body.get("long") or False,
        )
        await self.consumer.send_success({"results": result})

    @command("auditlog.list")
    @require_event_permission(Permission.EVENT_UPDATE)
    async def auditlog_get(self, body):
        result = await get_audit_log(
            self.consumer.event,
        )
        await self.consumer.send_success({"results": result})

    @command("report.generate.roomviews")
    @require_event_permission(Permission.EVENT_GRAPHS)
    async def roomviews_generate(self, body):
        result = await sync_to_async(generate_room_views.apply_async)(
            kwargs={"event": str(self.consumer.event.id), "input": body}
        )
        await self.consumer.send_success({"resultid": str(result.id)})

    @command("report.generate.sessionviews")
    @require_event_permission(Permission.EVENT_GRAPHS)
    async def sessionviews_generate(self, body):
        result = await sync_to_async(generate_session_views.apply_async)(
            kwargs={"event": str(self.consumer.event.id), "input": body}
        )
        await self.consumer.send_success({"resultid": str(result.id)})

    @command("report.generate.views")
    @require_event_permission(Permission.EVENT_GRAPHS)
    async def views_generate(self, body):
        result = await sync_to_async(generate_views.apply_async)(
            kwargs={"event": str(self.consumer.event.id), "input": body}
        )
        await self.consumer.send_success({"resultid": str(result.id)})

    @command("report.generate.summary")
    @require_event_permission(Permission.EVENT_GRAPHS)
    async def report_generate(self, body):
        result = await sync_to_async(generate_report.apply_async)(
            kwargs={"event": str(self.consumer.event.id), "input": body}
        )
        await self.consumer.send_success({"resultid": str(result.id)})

    @command("report.generate.question_history")
    @require_event_permission(
        Permission.EVENT_UPDATE
    )
    async def question_history_generate(self, body):
        result = await sync_to_async(generate_question_history.apply_async)(
            kwargs={"event": str(self.consumer.event.id), "input": body}
        )
        await self.consumer.send_success({"resultid": str(result.id)})

    @command("report.generate.poll_history")
    @require_event_permission(Permission.EVENT_UPDATE)
    async def question_poll_generate(self, body):
        result = await sync_to_async(generate_poll_history.apply_async)(
            kwargs={"event": str(self.consumer.event.id), "input": body}
        )
        await self.consumer.send_success({"resultid": str(result.id)})

    @command("report.generate.chat_history")
    @require_event_permission(Permission.EVENT_UPDATE)
    async def chat_history_generate(self, body):
        result = await sync_to_async(generate_chat_history.apply_async)(
            kwargs={"event": str(self.consumer.event.id), "input": body}
        )
        await self.consumer.send_success({"resultid": str(result.id)})

    @command("report.generate.attendee_list")
    @require_event_permission(Permission.EVENT_GRAPHS)
    async def attendee_list_generate(self, body):
        result = await sync_to_async(generate_attendee_list.apply_async)(
            kwargs={"event": str(self.consumer.event.id), "input": body}
        )
        await self.consumer.send_success({"resultid": str(result.id)})

    @command("report.generate.attendee_session_list")
    @require_event_permission(Permission.EVENT_GRAPHS)
    async def attendee_session_list_generate(self, body):
        result = await sync_to_async(generate_attendee_session_list.apply_async)(
            kwargs={"event": str(self.consumer.event.id), "input": body}
        )
        await self.consumer.send_success({"resultid": str(result.id)})

    @sync_to_async
    def _get_task_result(self, taskid):
        r = AsyncResult(taskid)
        if not r.ready():
            return False, None
        if not r.successful():
            r.maybe_throw()
        return True, r.result

    @command("report.status")
    @require_event_permission(Permission.EVENT_GRAPHS)
    async def report_status(self, body):
        ready, result = await self._get_task_result(body.get("resultid"))
        if not ready:
            await self.consumer.send_success({"ready": ready})
        else:
            await self.consumer.send_success({"ready": ready, "result": result})
