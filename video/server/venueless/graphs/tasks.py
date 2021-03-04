from datetime import timedelta
from io import BytesIO

import pytz
from django.core.files.base import ContentFile
from django.utils.timezone import now
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from venueless.celery_app import app
from venueless.core.models import Channel
from venueless.core.tasks import WorldTask
from venueless.graphs.report import ReportGenerator
from venueless.storage.models import StoredFile


@app.task(base=WorldTask)
def generate_report(world, input=None):
    cf = ReportGenerator(world).build(input)
    return cf.file.url


@app.task(base=WorldTask)
def generate_attendee_list(world, input=None):
    io = BytesIO()

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Attendees")
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 40
    ws.column_dimensions["D"].width = 30
    for j, f in enumerate(world.config.get("profile_fields", [])):
        ws.column_dimensions[get_column_letter(5 + j)].width = 30

    header = ["Internal ID", "External ID", "Name", "Permission traits"]
    for f in world.config.get("profile_fields", []):
        header.append(f.get("label"))
    ws.append(header)

    for i, u in enumerate(world.user_set.all()):
        ws.append(
            [
                str(u.pk),
                str(u.token_id) if u.token_id else "",
                u.profile.get("display_name") or "",
                ",".join(t for t in u.traits),
            ]
            + [
                u.profile.get("fields", {}).get(f.get("id") or f.get("label")) or ""
                for j, f in enumerate(world.config.get("profile_fields", []))
            ]
        )

    wb.save(io)
    io.seek(0)

    sf = StoredFile.objects.create(
        world=world,
        date=now(),
        filename="report.xlsx",
        expires=now() + timedelta(hours=2),
        type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        public=True,
        user=None,
    )
    sf.file.save("report.xlsx", ContentFile(io.read()))
    return sf.file.url


@app.task(base=WorldTask)
def generate_chat_history(world, input=None):
    channel = Channel.objects.get(pk=input.get("channel"))
    tz = pytz.timezone(world.timezone)
    io = BytesIO()

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Messages")
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 15
    ws.column_dimensions["B"].width = 15
    ws.column_dimensions["C"].width = 40
    ws.column_dimensions["D"].width = 60

    header = ["Date", "Time", "Sender", "Content"]
    ws.append(header)

    for e in (
        channel.chat_events.filter(event_type="channel.message")
        .select_related("sender")
        .order_by("timestamp")
    ):
        if e.content.get("type") == "text":
            msg = e.content.get("body")
        elif e.content.get("type") == "files":
            msg = "\n".join(f.get("url") for f in e.content.get("files"))
            if e.content.get("body"):
                msg = e.content.get("body") + "\n" + msg
        else:
            msg = "<unknown message type>"
        ws.append(
            [
                e.timestamp.astimezone(tz).date(),
                e.timestamp.astimezone(tz).time(),
                e.sender.profile.get("display_name", ""),
                msg,
            ]
        )

    wb.save(io)
    io.seek(0)

    sf = StoredFile.objects.create(
        world=world,
        date=now(),
        filename="report.xlsx",
        expires=now() + timedelta(hours=2),
        type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        public=True,
        user=None,
    )
    sf.file.save("report.xlsx", ContentFile(io.read()))
    return sf.file.url
