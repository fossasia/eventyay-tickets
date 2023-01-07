import datetime as dt
from urllib.parse import unquote

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.utils.timezone import now
from django.views.decorators.cache import cache_page
from django.views.decorators.http import condition
from i18nfield.utils import I18nJSONEncoder

from pretalx.agenda.views.schedule import ScheduleView
from pretalx.common.tasks import generate_widget_css, generate_widget_js
from pretalx.common.utils import language
from pretalx.common.views import conditional_cache_page
from pretalx.schedule.exporters import ScheduleData


def widget_css_etag(request, **kwargs):
    return request.event.settings.widget_css_checksum


def widget_js_etag(request, event, version, locale="en", **kwargs):
    return request.event.settings.get(f"widget_checksum_{version}_{locale}")


def widget_data_etag(request, **kwargs):
    return request.event.settings.widget_data_checksum


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


def cache_control(request, event, version=None):
    """We don't want cache headers on unversioned and WIP schedule sites.

    This differs from where we actually cache: We cache unversioned
    sites, but we don't want clients to know about it, to make sure
    they'll get the most recent content upon cache invalidation.
    """
    if version:
        if version == "wip":
            return False
        return True
    return False


def cache_version(request, event, version=None):
    """We want to cache all pages except for the WIP schedule site.

    Note that unversioned pages will be cached, but no cache headers
    will be sent to make sure users will always see the most recent
    changes.
    """
    if version and version == "wip":
        return False
    return True


def version_prefix(request, event, version=None):
    """On non-versioned pages, we want cache-invalidation on schedule
    relese."""
    if not version and request.event.current_schedule:
        return request.event.current_schedule.version


@conditional_cache_page(
    60, cache_version, cache_control=cache_control, key_prefix=version_prefix
)
def widget_data_v2(request, event, version=None):
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
@cache_page(60)
def widget_script(request, event, locale=None, version=2):
    """The locale parameter is only relevant to the deprecated v1 version of
    the widget."""
    if not request.user.has_perm("agenda.view_widget", request.event):
        raise Http404()
    if locale and locale not in [lc[:2] for lc, ll in settings.LANGUAGES]:
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
