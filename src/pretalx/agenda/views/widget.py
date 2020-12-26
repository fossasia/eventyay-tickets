import datetime as dt
from urllib.parse import unquote

import pytz
from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.utils.timezone import now
from django.views.decorators.cache import cache_page
from django.views.decorators.http import condition
from i18nfield.utils import I18nJSONEncoder

from pretalx.agenda.views.schedule import ScheduleView
from pretalx.common.tasks import generate_widget_css, generate_widget_js
from pretalx.common.utils import language
from pretalx.schedule.exporters import ScheduleData


def widget_css_etag(request, **kwargs):
    return request.event.settings.widget_css_checksum


def widget_js_etag(request, event, locale, version, **kwargs):
    return request.event.settings.get(f"widget_checksum_{version}_{locale}")


def widget_data_etag(request, **kwargs):
    return request.event.settings.widget_data_checksum


class WidgetData(ScheduleView):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("agenda.view_widget", request.event):
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get_schedule_data_proportional(self, data):
        timezone = pytz.timezone(self.request.event.timezone)
        max_rooms = 0
        for date in data:
            if date.get("first_start") and date.get("last_end"):
                start = (
                    date.get("first_start")
                    .astimezone(timezone)
                    .replace(second=0, minute=0)
                )
                end = date.get("last_end").astimezone(timezone)
                height_seconds = (end - start).total_seconds()
                date["display_start"] = start
                date["height"] = int(height_seconds / 60 * 2)
                date["hours"] = []
                step = start
                while step < end:
                    date["hours"].append(step.strftime("%H:%M"))
                    step += dt.timedelta(hours=1)
                max_rooms = max(max_rooms, len(date["rooms"]))
                for room in date["rooms"]:
                    for talk in room.get("talks", []):
                        talk.top = int(
                            (talk.start.astimezone(timezone) - start).total_seconds()
                            / 60
                            * 2
                        )
                        talk.height = int(talk.duration * 2)
                        talk.is_active = talk.start <= now() <= talk.real_end
        return {"data": list(data), "max_rooms": max_rooms}

    def get(self, request, *args, **kwargs):
        locale = request.GET.get("locale", "en")
        with language(locale):
            data = ScheduleData(
                event=self.request.event,
                schedule=self.schedule,
                with_accepted=False,
                with_breaks=True,
            ).data
            schedule = self.get_schedule_data_proportional(data)["data"]
            for day in schedule:
                for room in day["rooms"]:
                    room["name"] = str(room["name"])
                    room["talks"] = [
                        {
                            "title": talk.submission.title
                            if talk.submission
                            else str(talk.description),
                            "code": talk.submission.code if talk.submission else None,
                            "display_speaker_names": talk.submission.display_speaker_names
                            if talk.submission
                            else None,
                            "speakers": [
                                {"name": speaker.name, "code": speaker.code}
                                for speaker in talk.submission.speakers.all()
                            ]
                            if talk.submission
                            else None,
                            "height": talk.height,
                            "top": talk.top,
                            "start": talk.start,
                            "end": talk.end,
                            "do_not_record": talk.submission.do_not_record
                            if talk.submission
                            else None,
                            "track": getattr(talk.submission.track, "name", "")
                            if talk.submission
                            else None,
                        }
                        for talk in room["talks"]
                    ]
            response = JsonResponse(
                {
                    "schedule": schedule,
                    "event": {
                        "url": request.event.urls.schedule.full(),
                        "tracks": [
                            {"name": track.name, "color": track.color}
                            for track in request.event.tracks.all()
                        ],
                    },
                },
                encoder=I18nJSONEncoder,
            )
            response["Access-Control-Allow-Origin"] = "*"
            return response


@condition(etag_func=widget_data_etag)
@cache_page(60)
def widget_data_v2(request, event):
    event = request.event
    if not request.user.has_perm("agenda.view_widget", event):
        raise Http404()

    version = unquote(request.GET.get("v") or "")
    schedule = None
    if version and version == "wip":
        if not request.user.has_perm("orga.view_schedule", event):
            raise Http404()
        schedule = request.event.wip_schedule
    elif version:
        schedule = event.schedules.filter(version__iexact=version).first()

    schedule = schedule or event.current_schedule
    if not schedule:
        raise Http404()

    if schedule.version:
        talks = schedule.talks.filter(is_visible=True)
    else:
        talks = schedule.talks.filter(
            submission__state="confirmed", start__isnull=False, room__isnull=False
        )

    talks = (
        talks.select_related(
            "submission", "room", "submission__track"
        ).prefetch_related("submission__speakers")
    ).order_by("start")
    rooms = set()
    tracks = set()
    speakers = set()
    result = {
        "talks": [],
        "version": schedule.version,
        "timezone": event.timezone,
    }
    for talk in talks:
        rooms.add(talk.room)
        if talk.submission:
            tracks.add(talk.submission.track)
            speakers |= set(talk.submission.speakers.all())
            result["talks"].append(
                {
                    "code": talk.submission.code if talk.submission else None,
                    "title": talk.submission.title
                    if talk.submission
                    else talk.description,
                    "abstract": talk.submission.abstract if talk.submission else None,
                    "speakers": talk.submission.speakers.values_list("code", flat=True)
                    if talk.submission
                    else None,
                    "track": talk.submission.track_id if talk.submission else None,
                    "start": talk.start.astimezone(event.tz),
                    "end": talk.end.astimezone(event.tz),
                    "room": talk.room_id,
                }
            )
        else:
            result["talks"].append(
                {
                    "title": talk.description,
                    "start": talk.start,
                    "end": talk.end,
                    "room": talk.room_id,
                }
            )

    result["tracks"] = [
        {
            "id": track.id,
            "name": track.name,
            "color": track.color,
        }
        for track in tracks
        if track
    ]
    result["rooms"] = [
        {
            "id": room.id,
            "name": room.name,
        }
        for room in event.rooms.all()
        if room in rooms
    ]
    result["speakers"] = [
        {
            "code": user.code,
            "name": user.name,
            "avatar": user.get_avatar_url(),
        }
        for user in speakers
    ]

    response = JsonResponse(result, encoder=I18nJSONEncoder)
    response["Access-Control-Allow-Origin"] = "*"
    return response


@condition(etag_func=widget_js_etag)
@cache_page(60)
def widget_script(request, event, locale=None, version=2):
    """The locale parameter is only relevant to the deprecated v1 version of
    the widget."""
    if not request.user.has_perm("agenda.view_widget", request.event):
        raise Http404()
    if locale and locale not in [lc for lc, ll in settings.LANGUAGES]:
        raise Http404()

    fname = f"widget_file_{version}"
    if locale:
        fname = "{fname}_{locale}"
    existing_file = request.event.settings.get(fname)
    if existing_file and not settings.DEBUG:  # pragma: no cover
        return HttpResponse(existing_file.read(), content_type="text/javascript")

    data = generate_widget_js(
        request.event, locale=locale, save=not settings.DEBUG, version=version
    )
    return HttpResponse(data, content_type="text/javascript")


@condition(etag_func=widget_css_etag)
@cache_page(60)
def widget_style(request, event, version):
    if not request.user.has_perm("agenda.view_widget", request.event):
        raise Http404()
    existing_file = request.event.settings.widget_css
    if existing_file and not settings.DEBUG:  # pragma: no cover
        return HttpResponse(existing_file.read(), content_type="text/css")

    data = generate_widget_css(request.event, save=not settings.DEBUG)
    return HttpResponse(data, content_type="text/css")
