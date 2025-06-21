import datetime as dt
import hashlib
from urllib.parse import unquote

from csp.decorators import csp_exempt
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse, JsonResponse
from django.utils.timezone import now
from django.views.decorators.cache import cache_page
from django.views.decorators.http import condition
from i18nfield.utils import I18nJSONEncoder

from pretalx.agenda.permissions import is_agenda_visible, is_widget_always_visible
from pretalx.agenda.views.schedule import ScheduleView
from pretalx.common.language import language
from pretalx.common.views import conditional_cache_page
from pretalx.schedule.exporters import ScheduleData

WIDGET_JS_CHECKSUM = None
WIDGET_PATH = "agenda/js/pretalx-schedule.min.js"


def color_etag(request, event, **kwargs):
    return request.event.primary_color or "none"


def widget_js_etag(request, event, **kwargs):
    # The widget is stable across all events, we just return a checksum of the JS file
    # to make sure clients reload the widget when it changes.
    global WIDGET_JS_CHECKSUM
    if not WIDGET_JS_CHECKSUM:
        file_path = finders.find(WIDGET_PATH)
        with open(file_path, encoding="utf-8") as fp:
            WIDGET_JS_CHECKSUM = hashlib.md5(fp.read().encode()).hexdigest()
    return WIDGET_JS_CHECKSUM


class WidgetData(ScheduleView):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("agenda.view_widget", request.event):
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get_schedule_data_proportional(self, data):
        timezone = self.request.event.tz
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
                            (talk.local_start - start).total_seconds() / 60 * 2
                        )
                        talk.height = int(talk.duration * 2)
                        talk.is_active = talk.start <= now() <= talk.real_end
        return {"data": list(data), "max_rooms": max_rooms}

    @csp_exempt
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
                            "title": (
                                talk.submission.title
                                if talk.submission
                                else str(talk.description)
                            ),
                            "code": talk.submission.code if talk.submission else None,
                            "display_speaker_names": (
                                talk.submission.display_speaker_names
                                if talk.submission
                                else None
                            ),
                            "speakers": (
                                [
                                    {"name": speaker.name, "code": speaker.code}
                                    for speaker in talk.submission.speakers.all()
                                ]
                                if talk.submission
                                else None
                            ),
                            "height": talk.height,
                            "top": talk.top,
                            "start": talk.start,
                            "end": talk.end,
                            "do_not_record": (
                                talk.submission.do_not_record
                                if talk.submission
                                else None
                            ),
                            "track": (
                                getattr(talk.submission.track, "name", "")
                                if talk.submission
                                else None
                            ),
                            "featured": talk.submission.is_featured,
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


def is_public_and_versioned(request, event, version=None):
    if version and version == "wip":
        # We never cache the wip schedule
        return False
    if not (
        is_widget_always_visible(None, request.event)
        or is_agenda_visible(None, request.event)
    ):
        # This will be either a 404, or a page only accessible to the user
        # due to their logged-in status, so we don't want to cache it.
        return False
    return True


def version_prefix(request, event, version=None):
    """On non-versioned pages, we want cache-invalidation on schedule
    release."""
    if not version and request.event.current_schedule:
        return request.event.current_schedule.version
    return version


@conditional_cache_page(
    60,
    key_prefix=version_prefix,
    condition=is_public_and_versioned,
    server_timeout=5 * 60,
    headers={
        "Access-Control-Allow-Headers": "authorization,content-type",
        "Access-Control-Allow-Origin": "*",
    },
)
@csp_exempt
def widget_data(request, event, version=None):
    # Caching this page is tricky: We need the user to occasionally
    # ask for new data, and we definitely need to give them new data on schedule
    # release. This is because some information can change at any time, not just
    # in a new schedule version (like talk titles, speaker info etc).
    # So we:
    #  - tell the user a relatively short cache time that is safe to completely
    #    ignore new data for (1 minute)
    #  - simultaneously build a server-side cache that is invalidated on schedule
    #    release (by using the schedule version as key prefix), and that we keep
    #    around for a longer time (5 minutes), and that will be used for all users
    #  - also save a checksum of this server-side cache, and hand it to the client
    #    as an eTag, so they can ask for new data without it being too expensive
    #    on the server side
    # All this can ONLY take place if the schedule *has* a version (never caching
    # the WIP schedule page), and if anonymous users can see the schedule.
    event = request.event
    if request.method == "OPTIONS":
        response = JsonResponse({})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Headers"] = "authorization,content-type"
        return response
    if not request.user.has_perm("agenda.view_widget", event):
        raise Http404()

    version = version or unquote(request.GET.get("v") or "")
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

    result = schedule.build_data(all_talks=not schedule.version)
    response = JsonResponse(result, encoder=I18nJSONEncoder)
    response["Access-Control-Allow-Headers"] = "authorization,content-type"
    response["Access-Control-Allow-Origin"] = "*"
    return response


@condition(etag_func=widget_js_etag)
@csp_exempt
def widget_script(request, event):
    # This page basically just serves a static file under a known path (ideally, the
    # administrators could and should even turn on gzip compression for the
    # /<event>/widget/schedule.js path, as it cuts down the transferred data
    # by about 80% for the schedule.js file, which is the largest file on the
    # main schedule page).
    if not request.user.has_perm("agenda.view_widget", request.event):
        raise Http404()

    file_path = finders.find(WIDGET_PATH)
    with open(file_path, encoding="utf-8") as fp:
        code = fp.read()
    data = code.encode()
    return HttpResponse(data, content_type="text/javascript")


@condition(etag_func=color_etag)
@cache_page(60 * 60)
@csp_exempt
def event_css(request, event):
    # If this event has custom colours, we send back a simple CSS file that sets the
    # root colours for the event.
    result = ""
    if request.event.primary_color:
        if request.GET.get("target") == "orga":
            # The organiser area sometimes needs the event’s colour, but shouldn’t use
            # it as primary colour automatically.
            result = (
                ":root {"
                + f"--color-primary-event: {request.event.primary_color};"
                + "}"
            )
        else:
            result = (
                ":root {" + f"--color-primary: {request.event.primary_color};" + "}"
            )
    return HttpResponse(result, content_type="text/css")
