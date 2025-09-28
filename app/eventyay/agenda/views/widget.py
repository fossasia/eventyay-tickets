import hashlib
from urllib.parse import unquote

from csp.decorators import csp_exempt
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import condition
from i18nfield.utils import I18nJSONEncoder

from eventyay.talk_rules.agenda import is_widget_visible
from eventyay.common.views import conditional_cache_page

WIDGET_JS_CHECKSUM = None
WIDGET_PATH = 'agenda/js/pretalx-schedule.min.js'


def color_etag(request, event, **kwargs):
    return request.event.primary_color or 'none'


def widget_js_etag(request, event, **kwargs):
    # The widget is stable across all events, we just return a checksum of the JS file
    # to make sure clients reload the widget when it changes.
    global WIDGET_JS_CHECKSUM
    if not WIDGET_JS_CHECKSUM:
        file_path = finders.find(WIDGET_PATH)
        with open(file_path, encoding='utf-8') as fp:
            WIDGET_JS_CHECKSUM = hashlib.md5(fp.read().encode()).hexdigest()
    return WIDGET_JS_CHECKSUM


def is_public_and_versioned(request, event, version=None):
    if version and version == 'wip':
        # We never cache the wip schedule
        return False
    if not is_widget_visible(None, request.event):
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
        'Access-Control-Allow-Headers': 'authorization,content-type',
        'Access-Control-Allow-Origin': '*',
    },
)
@csp_exempt()
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
    if request.method == 'OPTIONS':
        response = JsonResponse({})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'authorization,content-type'
        return response
    if not request.user.has_perm('schedule.view_widget_schedule', event):
        raise Http404()

    version = version or unquote(request.GET.get('v') or '')
    schedule = None
    if version and version == 'wip':
        if not request.user.has_perm('schedule.orga_view_schedule', event):
            raise Http404()
        schedule = request.event.wip_schedule
    elif version:
        schedule = event.schedules.filter(version__iexact=version).first()

    schedule = schedule or event.current_schedule
    if not schedule:
        raise Http404()

    result = schedule.build_data(all_talks=not schedule.version)
    response = JsonResponse(result, encoder=I18nJSONEncoder)
    response['Access-Control-Allow-Headers'] = 'authorization,content-type'
    response['Access-Control-Allow-Origin'] = '*'
    return response


@condition(etag_func=widget_js_etag)
@csp_exempt()
def widget_script(request, event):
    # This page basically just serves a static file under a known path (ideally, the
    # administrators could and should even turn on gzip compression for the
    # /<event>/widget/schedule.js path, as it cuts down the transferred data
    # by about 80% for the schedule.js file, which is the largest file on the
    # main schedule page).
    if not request.user.has_perm('schedule.view_widget_schedule', request.event):
        raise Http404()

    file_path = finders.find(WIDGET_PATH)
    with open(file_path, encoding='utf-8') as fp:
        code = fp.read()
    data = code.encode()
    return HttpResponse(data, content_type='text/javascript')


@condition(etag_func=color_etag)
@cache_page(5 * 60)
@csp_exempt()
def event_css(request, event):
    # If this event has custom colours, we send back a simple CSS file that sets the
    # root colours for the event.
    result = ''
    if request.event.primary_color:
        if request.GET.get('target') == 'orga':
            # The organizer area sometimes needs the event’s colour, but shouldn’t use
            # it as primary colour automatically.
            result = ':root {' + f'--color-primary-event: {request.event.primary_color};' + '}'
        else:
            result = ':root {' + f'--color-primary: {request.event.primary_color};' + '}'
    return HttpResponse(result, content_type='text/css')
