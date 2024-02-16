import datetime as dt
import json
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import vobject
from django.template.loader import get_template
from django.utils.functional import cached_property
from i18nfield.utils import I18nJSONEncoder

from pretalx import __version__
from pretalx.common.exporter import BaseExporter
from pretalx.common.urls import get_base_url


class ScheduleData(BaseExporter):
    def __init__(self, event, schedule=None, with_accepted=False, with_breaks=False):
        super().__init__(event)
        self.schedule = schedule
        self.with_accepted = with_accepted
        self.with_breaks = with_breaks

    @cached_property
    def metadata(self):
        if not self.schedule:
            return []

        return {
            "url": self.event.urls.schedule.full(),
            "base_url": get_base_url(self.event),
        }

    @cached_property
    def data(self):
        if not self.schedule:
            return []

        event = self.event
        schedule = self.schedule

        base_qs = (
            schedule.talks.all()
            if self.with_accepted
            else schedule.talks.filter(is_visible=True)
        )
        talks = (
            base_qs.select_related(
                "submission",
                "submission__event",
                "submission__submission_type",
                "submission__track",
                "room",
            )
            .prefetch_related("submission__speakers", "submission__resources")
            .order_by("start")
            .exclude(submission__state="deleted")
        )
        data = {
            current_date.date(): {
                "index": index + 1,
                "start": current_date.replace(hour=4, minute=0).astimezone(event.tz),
                "end": current_date.replace(hour=3, minute=59).astimezone(event.tz)
                + dt.timedelta(days=1),
                "first_start": None,
                "last_end": None,
                "rooms": {},
            }
            for index, current_date in enumerate(
                event.datetime_from + dt.timedelta(days=i)
                for i in range((event.date_to - event.date_from).days + 1)
            )
        }

        for talk in talks:
            if (
                not talk.start
                or not talk.room
                or (not talk.submission and not self.with_breaks)
            ):
                continue
            talk_date = talk.local_start.date()
            if talk.local_start.hour < 3 and talk_date != event.date_from:
                talk_date -= dt.timedelta(days=1)
            day_data = data.get(talk_date)
            if not day_data:
                continue
            if str(talk.room.name) not in day_data["rooms"]:
                day_data["rooms"][str(talk.room.name)] = {
                    "id": talk.room.id,
                    "guid": talk.room.uuid,
                    "name": talk.room.name,
                    "description": talk.room.description,
                    "position": talk.room.position,
                    "talks": [talk],
                }
            else:
                day_data["rooms"][str(talk.room.name)]["talks"].append(talk)
            if not day_data["first_start"] or talk.start < day_data["first_start"]:
                day_data["first_start"] = talk.start
            if not day_data["last_end"] or talk.local_end > day_data["last_end"]:
                day_data["last_end"] = talk.local_end

        for d in data.values():
            d["rooms"] = sorted(
                d["rooms"].values(),
                key=lambda room: (
                    room["position"] if room["position"] is not None else room["id"]
                ),
            )
        return data.values()


class FrabXmlExporter(ScheduleData):
    identifier = "schedule.xml"
    verbose_name = "XML (frab compatible)"
    public = True
    show_qrcode = True
    icon = "fa-code"
    cors = "*"

    def render(self, **kwargs):
        context = {
            "data": self.data,
            "metadata": self.metadata,
            "schedule": self.schedule,
            "event": self.event,
            "version": __version__,
            "base_url": get_base_url(self.event),
        }
        content = get_template("agenda/schedule.xml").render(context=context)
        return f"{self.event.slug}-schedule.xml", "text/xml", content


class FrabXCalExporter(ScheduleData):
    identifier = "schedule.xcal"
    verbose_name = "XCal (frab compatible)"
    public = True
    icon = "fa-calendar"
    cors = "*"

    def render(self, **kwargs):
        url = get_base_url(self.event)
        context = {"data": self.data, "url": url, "domain": urlparse(url).netloc}
        content = get_template("agenda/schedule.xcal").render(context=context)
        return f"{self.event.slug}.xcal", "text/xml", content


class FrabJsonExporter(ScheduleData):
    identifier = "schedule.json"
    verbose_name = "JSON (frab compatible)"
    public = True
    icon = "{ }"
    cors = "*"

    def get_data(self, **kwargs):
        schedule = self.schedule
        return {
            "url": self.metadata["url"],
            "version": schedule.version,
            "base_url": self.metadata["base_url"],
            "conference": {
                "acronym": self.event.slug,
                "title": str(self.event.name),
                "start": self.event.date_from.strftime("%Y-%m-%d"),
                "end": self.event.date_to.strftime("%Y-%m-%d"),
                "daysCount": self.event.duration,
                "timeslot_duration": "00:05",
                "time_zone_name": self.event.timezone,
                "colors": {"primary": self.event.primary_color or "#3aa57c"},
                "rooms": [
                    {
                        "name": str(room.name),
                        "guid": room.uuid,
                        "description": str(room.description) or None,
                        "capacity": room.capacity,
                    }
                    for room in self.event.rooms.all()
                ],
                "tracks": [
                    {
                        "name": str(track.name),
                        "color": track.color,
                    }
                    for track in self.event.tracks.all()
                ],
                "days": [
                    {
                        "index": day["index"],
                        "date": day["start"].strftime("%Y-%m-%d"),
                        "day_start": day["start"].astimezone(self.event.tz).isoformat(),
                        "day_end": day["end"].astimezone(self.event.tz).isoformat(),
                        "rooms": {
                            str(room["name"]): [
                                {
                                    "url": talk.submission.urls.public.full(),
                                    "id": talk.submission.id,
                                    "guid": talk.uuid,
                                    "date": talk.local_start.isoformat(),
                                    "start": talk.local_start.strftime("%H:%M"),
                                    "logo": (
                                        talk.submission.urls.image.full()
                                        if talk.submission.image
                                        else None
                                    ),
                                    "duration": talk.export_duration,
                                    "room": str(room["name"]),
                                    "slug": talk.frab_slug,
                                    "title": talk.submission.title,
                                    "subtitle": "",
                                    "track": (
                                        str(talk.submission.track.name)
                                        if talk.submission.track
                                        else None
                                    ),
                                    "type": str(talk.submission.submission_type.name),
                                    "language": talk.submission.content_locale,
                                    "abstract": talk.submission.abstract,
                                    "description": talk.submission.description,
                                    "recording_license": "",
                                    "do_not_record": talk.submission.do_not_record,
                                    "persons": [
                                        {
                                            "guid": person.guid,
                                            "id": person.id,
                                            "code": person.code,
                                            "public_name": person.get_display_name(),
                                            "avatar": person.get_avatar_url(self.event)
                                            or None,
                                            "biography": getattr(
                                                person.profiles.filter(
                                                    event=self.event
                                                ).first(),
                                                "biography",
                                                "",
                                            ),
                                            "answers": (
                                                [
                                                    {
                                                        "question": answer.question.id,
                                                        "answer": answer.answer,
                                                        "options": [
                                                            option.answer
                                                            for option in answer.options.all()
                                                        ],
                                                    }
                                                    for answer in person.answers.all()
                                                ]
                                                if getattr(self, "is_orga", False)
                                                else []
                                            ),
                                        }
                                        for person in talk.submission.speakers.all()
                                    ],
                                    "links": [],
                                    "attachments": [],
                                    "answers": (
                                        [
                                            {
                                                "question": answer.question.id,
                                                "answer": answer.answer,
                                                "options": [
                                                    option.answer
                                                    for option in answer.options.all()
                                                ],
                                            }
                                            for answer in talk.submission.answers.all()
                                        ]
                                        if getattr(self, "is_orga", False)
                                        else []
                                    ),
                                }
                                for talk in room["talks"]
                            ]
                            for room in day["rooms"]
                        },
                    }
                    for day in self.data
                ],
            },
        }

    def render(self, **kwargs):
        content = self.get_data()
        return (
            f"{self.event.slug}.json",
            "application/json",
            json.dumps(
                {
                    "$schema": "https://c3voc.de/schedule/schema.json",
                    "generator": {"name": "pretalx", "version": __version__},
                    "schedule": content,
                },
                cls=I18nJSONEncoder,
            ),
        )


class ICalExporter(BaseExporter):
    identifier = "schedule.ics"
    verbose_name = "iCal"
    public = True
    show_qrcode = True
    icon = "fa-calendar"
    cors = "*"

    def __init__(self, event, schedule=None):
        super().__init__(event)
        self.schedule = schedule

    def render(self, **kwargs):
        netloc = urlparse(get_base_url(self.event)).netloc
        cal = vobject.iCalendar()
        cal.add("prodid").value = f"-//pretalx//{netloc}//"
        creation_time = dt.datetime.now(ZoneInfo("UTC"))

        talks = (
            self.schedule.talks.filter(is_visible=True)
            .prefetch_related("submission__speakers")
            .select_related("submission", "room", "submission__event")
            .order_by("start")
        )
        for talk in talks:
            talk.build_ical(cal, creation_time=creation_time, netloc=netloc)

        return f"{self.event.slug}.ics", "text/calendar", cal.serialize()
