import datetime as dt
import json
import xml.etree.ElementTree as ElementTree
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import vobject
from django.conf import settings
from django.template.loader import get_template
from django.utils.functional import cached_property
from django.utils.safestring import SafeString
from django.utils.translation import gettext_lazy as _
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
            .prefetch_related("submission__speakers")
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
                event.datetime_from + dt.timedelta(days=days)
                for days in range((event.date_to - event.date_from).days + 1)
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

        for day in data.values():
            day["rooms"] = sorted(
                day["rooms"].values(),
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
    favs_retrieve = False
    talk_ids = []
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
        if self.favs_retrieve:
            root = ElementTree.fromstring(content)
            for day in root.findall("day"):
                for room in day.findall("room"):
                    for event in room.findall("event"):
                        event_slug = event.find("url").text.split("/")[-2]
                        if event_slug not in self.talk_ids:
                            room.remove(event)
            filtered_xml_data = ElementTree.tostring(root, encoding="unicode")
            content = SafeString(filtered_xml_data)
        return f"{self.event.slug}-schedule.xml", "text/xml", content


class MyFrabXmlExporter(FrabXmlExporter):
    identifier = "schedule-my.xml"
    verbose_name = "My ⭐ Sessions XML"
    favs_retrieve = True


class FrabXCalExporter(ScheduleData):
    identifier = "schedule.xcal"
    verbose_name = "XCal (frab compatible)"
    public = True
    favs_retrieve = False
    talk_ids = []
    icon = "fa-calendar"
    cors = "*"

    def render(self, **kwargs):
        url = get_base_url(self.event)
        context = {"data": self.data, "url": url, "domain": urlparse(url).netloc}
        content = get_template("agenda/schedule.xcal").render(context=context)
        if self.favs_retrieve:
            root = ElementTree.fromstring(content)
            for vcalendar in root.findall("vcalendar"):
                for vevent in vcalendar.findall("vevent"):
                    event_uid = vevent.find("uid").text.split("@@")[0]
                    if event_uid not in self.talk_ids:
                        vcalendar.remove(vevent)
            filtered_xcal_data = ElementTree.tostring(root, encoding="unicode")
            content = SafeString(filtered_xcal_data)
        return f"{self.event.slug}.xcal", "text/xml", content


class MyFrabXCalExporter(FrabXCalExporter):
    identifier = "schedule-my.xcal"
    verbose_name = "My ⭐ Sessions XCAL"
    favs_retrieve = True


class FrabJsonExporter(ScheduleData):
    identifier = "schedule.json"
    verbose_name = "JSON (frab compatible)"
    public = True
    favs_retrieve = False
    talk_ids = []
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
                "colors": {"primary": self.event.primary_color or "#2185d0"},
                "rooms": [
                    {
                        "name": str(room.name),
                        "slug": room.slug,
                        # TODO room url
                        "guid": room.uuid,
                        "description": str(room.description) or None,
                        "capacity": room.capacity,
                    }
                    for room in self.event.rooms.all()
                ],
                "tracks": [
                    {
                        "name": str(track.name),
                        "slug": track.slug,
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
                                    "guid": talk.uuid,
                                    "code": talk.submission.code,
                                    "id": talk.submission.id,
                                    "logo": (
                                        talk.submission.urls.image.full()
                                        if talk.submission.image
                                        else None
                                    ),
                                    "date": talk.local_start.isoformat(),
                                    "start": talk.local_start.strftime("%H:%M"),
                                    "duration": talk.export_duration,
                                    "room": str(room["name"]),
                                    "slug": talk.frab_slug,
                                    "url": talk.submission.urls.public.full(),
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
                                            "code": person.code,
                                            "name": person.get_display_name(),
                                            "avatar": person.get_avatar_url(self.event)
                                            or None,
                                            "biography": person.event_profile(
                                                self.event
                                            ).biography,
                                            "public_name": person.get_display_name(),  # deprecated
                                            "guid": person.guid,
                                            "url": person.event_profile(
                                                self.event
                                            ).urls.public.full(),
                                        }
                                        for person in talk.submission.speakers.all()
                                    ],
                                    "links": [
                                        {
                                            "title": resource.description,
                                            "url": resource.link,
                                            "type": "related",
                                        }
                                        for resource in talk.submission.resources.all()
                                        if resource.link
                                    ],
                                    "feedback_url": talk.submission.urls.feedback.full(),
                                    "origin_url": talk.submission.urls.public.full(),
                                    "attachments": [
                                        {
                                            "title": resource.description,
                                            "url": resource.resource.url,
                                            "type": "related",
                                        }
                                        for resource in talk.submission.resources.all()
                                        if not resource.link
                                    ],
                                }
                                for talk in room["talks"]
                                if (
                                    self.favs_retrieve is True
                                    and talk.submission.code in self.talk_ids
                                )
                                or not self.favs_retrieve
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


class MyFrabJsonExporter(FrabJsonExporter):
    identifier = "schedule-my.json"
    verbose_name = "My ⭐ Sessions JSON"
    favs_retrieve = True


class ICalExporter(BaseExporter):
    identifier = "schedule.ics"
    verbose_name = _("iCal (full event)")
    public = True
    show_public = False
    show_qrcode = True
    favs_retrieve = False
    talk_ids = []
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
            if talk.submission and talk.submission.code not in self.talk_ids:
                continue
            talk.build_ical(cal, creation_time=creation_time, netloc=netloc)

        return f"{self.event.slug}.ics", "text/calendar", cal.serialize()


class MyICalExporter(ICalExporter):
    identifier = "schedule-my.ics"
    verbose_name = "My ⭐ Sessions iCal"
    favs_retrieve = True


class FavedICalExporter(BaseExporter):
    identifier = "faved.ics"
    verbose_name = _("iCal (your starred sessions)")
    show_qrcode = False
    icon = "fa-calendar"
    show_public = True
    cors = "*"

    def is_public(self, request, **kwargs):
        return (
            "agenda" in request.resolver_match.namespaces
            and request.user.is_authenticated
            and request.user.has_perm("schedule.list_schedule", request.event)
        )

    def render(self, request, **kwargs):
        if not request.user.is_authenticated:
            return None

        netloc = urlparse(settings.SITE_URL).netloc
        slots = request.event.current_schedule.scheduled_talks.filter(
            submission__favourites__user__in=[request.user]
        )

        cal = vobject.iCalendar()
        cal.add("prodid").value = f"-//pretalx//{netloc}//{request.event.slug}//faved"

        for slot in slots:
            slot.build_ical(cal)
        return f"{self.event.slug}-favs.ics", "text/calendar", cal.serialize()
