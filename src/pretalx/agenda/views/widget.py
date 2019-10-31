import hashlib

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import condition
from i18nfield.utils import I18nJSONEncoder

from pretalx.agenda.views.schedule import ScheduleView
from pretalx.common.tasks import generate_widget_css
from pretalx.common.utils import language


def widget_css_etag(request, **kwargs):
    return request.event.settings.widget_css_checksum


def widget_js_etag(request, locale, **kwargs):
    return request.event.settings.get(f'widget_checksum_{locale}')


class WidgetData(ScheduleView):
    def get(self, request, *args, **kwargs):
        if not request.user.has_perm('agenda.view_widget'):
            return Http404()
        locale = request.GET.get('locale', 'en')
        with language(locale):
            schedule = list(self.get_schedule_data()[0])
            for day in schedule:
                for room in day['rooms']:
                    room['talks'] = [
                        {
                            'title': talk.submission.title,
                            'code': talk.submission.code,
                            'display_speaker_names': talk.submission.display_speaker_names,
                            'speakers': [
                                {
                                    'name': speaker.name,
                                    'code': speaker.code
                                } for speaker in talk.submission.speakers.all()
                            ],
                            'height': talk.height,
                            'top': talk.top,
                            'start': talk.start,
                            'end': talk.end,
                            'do_not_record': talk.submission.do_not_record,
                            'track': getattr(talk.submission.track, 'name', ''),
                        }
                        for talk in room['talks']
                    ]
            response = JsonResponse(
                {
                    'schedule': schedule,
                    'event': {
                        'url': request.event.urls.schedule.full(),
                        'tracks': [{'name': track.name, 'color': track.color} for track in request.event.tracks.all()],
                    }
                },
                encoder=I18nJSONEncoder,
            )
            response['Access-Control-Allow-Origin'] = '*'
            return response


def generate_widget_js(event, locale):
    code = f'''
const lang = "{locale}";
let dataSource = "{event.urls.widget_data_source}";
'''
    files = [
        'vendored/vue.js' if settings.DEBUG else 'vendored/vue.min.js',
        'vendored/moment-with-locales.js',
        'agenda/js/widget.js',
    ]
    for fname in files:
        f = finders.find(fname)
        with open(f, 'r', encoding='utf-8') as fp:
            code += fp.read()

    return code


@condition(etag_func=widget_js_etag)
@cache_page(60)
def widget_script(request, event, locale):
    if not request.user.has_perm('agenda.view_widget'):
        return Http404()
    if locale not in [lc for lc, ll in settings.LANGUAGES]:
        raise Http404()

    existing_file = request.event.settings.get('widget_file_{}'.format(locale))
    if existing_file and not settings.DEBUG:
        return HttpResponse(default_storage.open(existing_file).read(), content_type='text/javascript')

    data = generate_widget_js(request.event, locale).encode()
    if not settings.DEBUG:
        checksum = hashlib.sha1(data).hexdigest()
        file_name = default_storage.save(
            'widget/widget.{}.{}.js'.format(locale, checksum),
            ContentFile(data)
        )
        request.event.settings.set('widget_file_{}'.format(locale), 'file://' + file_name)
        request.event.settings.set('widget_checksum_{}'.format(locale), checksum)
    return HttpResponse(data, content_type='text/javascript')


@condition(etag_func=widget_css_etag)
@cache_page(60)
def widget_style(request, event):
    if not request.user.has_perm('agenda.view_widget'):
        return Http404()
    existing_file = request.event.settings.widget_css
    if existing_file and not settings.DEBUG:
        return HttpResponse(default_storage.open(existing_file).read(), content_type='text/css')

    data = generate_widget_css(request.event, save=not settings.DEBUG)
    return HttpResponse(data, content_type='text/css')
