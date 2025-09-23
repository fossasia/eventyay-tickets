import importlib.util
import os

from django.apps import apps
from django.urls import include
from django.urls import re_path as url
from django.views.generic import TemplateView, View
from django.http import HttpResponse, Http404
from django.views.static import serve as static_serve
from django.conf import settings
from mimetypes import guess_type

from eventyay.config.urls import common_patterns
from eventyay.multidomain.plugin_handler import plugin_event_urls
from eventyay.presale.urls import (
    event_patterns,
    locale_patterns,
    organizer_patterns,
)
from eventyay.base.models import Event  # Added for /video event context

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WEBAPP_DIST_DIR = os.path.normpath(os.path.join(BASE_DIR, 'webapp', 'dist'))

class VideoSPAView(View):
    def get(self, request, *args, **kwargs):
        # event_identifier is optional; if provided we try pk first then slug
        event_identifier = kwargs.get('event_identifier')
        event = None
        if event_identifier:
            try:
                # pk lookup
                event = Event.objects.get(pk=event_identifier)
            except (Event.DoesNotExist, ValueError):  # ValueError if not int
                try:
                    event = Event.objects.get(slug=event_identifier)
                except Event.DoesNotExist:
                    event = None
        index_path = os.path.join(WEBAPP_DIST_DIR, 'index.html')
        if os.path.exists(index_path):
            with open(index_path, 'r') as f:
                content = f.read()
        else:
            content = '<!-- /video build missing: {} -->'.format(index_path)
        if event:
            # Inject window.venueless config (frontend still expects this name)
            # Mirror structure used in legacy live AppView but adjusted basePath
            from django.urls import reverse  # kept for other endpoints
            import json
            # Quick fix: avoid reverse('api:root') which is currently not included -> NoReverseMatch
            api_base = f"/api/v1/events/{event.pk}/"  # TODO replace with reverse once API namespace wired
            # Best effort reverse for optional endpoints
            def safe_reverse(name, **kw):
                try:
                    return reverse(name, kwargs=kw) if kw else reverse(name)
                except Exception:
                    return None
            # Safely access event.config which may be None
            cfg = event.config or {}
            injected = {
                'api': {
                    'base': api_base,
                    'socket': '{}://{}/ws/event/{}/'.format(
                        'wss' if request.is_secure() else 'ws',
                        request.get_host(),
                        event.pk,
                    ),
                    'upload': safe_reverse('storage:upload') or '',
                    'scheduleImport': safe_reverse('storage:schedule_import') or '',
                    'systemlog': safe_reverse('live:systemlog') or '',
                },
                'features': getattr(event, 'feature_flags', {}) or {},
                'externalAuthUrl': getattr(event, 'external_auth_url', None),
                'locale': event.locale,
                'date_locale': cfg.get('date_locale', 'en-ie'),
                'theme': cfg.get('theme', {}),
                'video_player': cfg.get('video_player', {}),
                'mux': cfg.get('mux', {}),
                # Extra values expected by config.js/theme
                'basePath': '/video',
                'defaultLocale': 'en',
                'locales': ['en', 'de', 'pt_BR', 'ar', 'fr', 'es', 'uk', 'ru'],
                'noThemeEndpoint': True,  # Prevent frontend from requesting missing /theme endpoint
            }
            # Always prepend to guarantee execution before any module scripts
            import json as _json
            content = f"<script>window.venueless={_json.dumps(injected)}</script>" + content
        elif event_identifier:
            # Event identifier provided but not found -> 404
            return HttpResponse('Event not found', status=404)
        resp = HttpResponse(content, content_type='text/html')
        resp._csp_ignore = True  # Disable CSP for SPA (relies on dynamic inline scripts)
        return resp

class VideoAssetView(View):
    def get(self, request, path='', *args, **kwargs):
        # Accept empty path -> index handling done by SPA view
        candidate_paths = [
            os.path.join(WEBAPP_DIST_DIR, path),
            os.path.join(WEBAPP_DIST_DIR, 'assets', path),
        ] if path else []
        for fp in candidate_paths:
            if os.path.isfile(fp):
                rel = os.path.relpath(fp, WEBAPP_DIST_DIR)
                resp = static_serve(request, rel, document_root=WEBAPP_DIST_DIR)
                resp._csp_ignore = True
                # Ensure proper content type for module scripts
                ctype, _ = guess_type(fp)
                if ctype:
                    resp['Content-Type'] = ctype
                return resp
        raise Http404()

presale_patterns_main = [
    url(
        r'',
        include(
            (
                locale_patterns
                + [
                    url(r'^(?P<organizer>[^/]+)/', include(organizer_patterns)),
                    url(
                        r'^(?P<organizer>[^/]+)/(?P<event>[^/]+)/',
                        include(event_patterns),
                    ),
                    url(
                        r'^$',
                        TemplateView.as_view(template_name='pretixpresale/index.html'),
                        name='index',
                    ),
                ],
                'presale',
            )
        ),
    )
]

raw_plugin_patterns = []
for app in apps.get_app_configs():
    if hasattr(app, 'EventyayPluginMeta'):
        if importlib.util.find_spec(app.name + '.urls'):
            urlmod = importlib.import_module(app.name + '.urls')
            single_plugin_patterns = []
            if hasattr(urlmod, 'urlpatterns'):
                single_plugin_patterns += urlmod.urlpatterns
            if hasattr(urlmod, 'event_patterns'):
                patterns = plugin_event_urls(urlmod.event_patterns, plugin=app.name)
                single_plugin_patterns.append(url(r'^(?P<organizer>[^/]+)/(?P<event>[^/]+)/', include(patterns)))
            if hasattr(urlmod, 'organizer_patterns'):
                patterns = urlmod.organizer_patterns
                single_plugin_patterns.append(url(r'^(?P<organizer>[^/]+)/', include(patterns)))
            raw_plugin_patterns.append(url(r'', include((single_plugin_patterns, app.label))))

plugin_patterns = [url(r'', include((raw_plugin_patterns, 'plugins')))]

# Adjust urlpatterns: add event_identifier aware pattern excluding assets
urlpatterns = common_patterns + [
    url(r'^video/assets/(?P<path>.*)$', VideoAssetView.as_view(), name='video.assets.legacy'),
    url(r'^video/(?P<path>[^?]*\.[a-zA-Z0-9._-]+)$', VideoAssetView.as_view(), name='video.assets'),
    # /video/<event_identifier>/... (exclude assets as identifier)
    url(r'^video/(?P<event_identifier>(?!assets)[^/]+)(?:/.*)?$', VideoSPAView.as_view(), name='video.event.index'),
    # Plain /video -> maybe show generic splash without event (currently same view without event)
    url(r'^video/?$', VideoSPAView.as_view(), name='video.index'),
] + presale_patterns_main + plugin_patterns

handler404 = 'eventyay.base.views.errors.page_not_found'
handler500 = 'eventyay.base.views.errors.server_error'
