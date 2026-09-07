import importlib.util
import logging

from django.apps import apps
from django.urls import include, path, re_path, reverse_lazy
from django.views.generic.base import RedirectView

from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)

# Ticket-video integration: plugin URLs are auto-included via plugin handler below.
from eventyay.config.urls import common_patterns
from eventyay.multidomain.plugin_handler import plugin_event_urls
from eventyay.presale.urls import (
    event_patterns,
    locale_patterns,
    organizer_patterns,
)
from eventyay.presale.views.startpage import (
    FollowedEventsView,
    PastEventsView,
    StartPageView,
    UpcomingEventsView,
)

from eventyay.control.views.pages import SystemPageView
from .views import AnonymousInviteRedirectView, VideoAssetView, VideoSPAView
from eventyay.plugins.ticketoutputpdf import urls as ticketoutputpdf_urls


logger = logging.getLogger(__name__)


presale_patterns_main = [
    path(
        '',
        include(
            (
                locale_patterns
                + [
                    path('upcoming/', UpcomingEventsView.as_view(), name='events.upcoming'),
                    path('past/', PastEventsView.as_view(), name='events.past'),
                    path('followed-events/', FollowedEventsView.as_view(), name='events.followed'),
                    path('all-events/upcoming/', RedirectView.as_view(url=reverse_lazy('presale:events.upcoming'), permanent=True)),
                    path('all-events/past/', RedirectView.as_view(url=reverse_lazy('presale:events.past'), permanent=True)),
                    path('all-events/', RedirectView.as_view(url=reverse_lazy('presale:index'), permanent=True)),
                    path('terms/', SystemPageView.as_view(slug='terms'), name='page.terms'),
                    path('privacy/', SystemPageView.as_view(slug='privacy'), name='page.privacy'),
                    path('pricing/', SystemPageView.as_view(slug='pricing'), name='page.pricing'),
                    path('support/', SystemPageView.as_view(slug='support'), name='page.support'),
                    path('<orgslug:organizer>/', include(organizer_patterns)),
                    path(
                        '<orgslug:organizer>/<slug:event>/',
                        include(event_patterns),
                    ),
                    path(
                        '',
                        StartPageView.as_view(),
                        name='index',
                    ),
                ],
                'presale',
            )
        ),
    )
]

# Plugin URL registration strategy:
# - Auto-discover any installed plugin that provides EventyayPluginMeta and URLs.

raw_plugin_patterns = []

# Auto-register installed plugins with EventyayPluginMeta
for app in apps.get_app_configs():
    if hasattr(app, 'EventyayPluginMeta'):
        if importlib.util.find_spec(f'{app.name}.urls'):
            try:
                urlmod = importlib.import_module(f'{app.name}.urls')
                single_plugin_patterns = []
                if hasattr(urlmod, 'urlpatterns'):
                    single_plugin_patterns += urlmod.urlpatterns
                if hasattr(urlmod, 'event_patterns'):
                    patterns = plugin_event_urls(urlmod.event_patterns, plugin=app.name)
                    single_plugin_patterns.append(path('<orgslug:organizer>/<slug:event>/', include(patterns)))
                if hasattr(urlmod, 'organizer_patterns'):
                    patterns = urlmod.organizer_patterns
                    single_plugin_patterns.append(path('<orgslug:organizer>/', include(patterns)))
                raw_plugin_patterns.append(path('', include((single_plugin_patterns, app.label))))
                logger.debug('Registered URLs under "%s" namespace:\n%s', app.label, single_plugin_patterns)
            except (ImportError, AttributeError, TypeError):
                logger.exception('Error loading plugin URLs for %s', app.name)

if hasattr(ticketoutputpdf_urls, 'urlpatterns'):
    raw_plugin_patterns.append(path('', include((ticketoutputpdf_urls.urlpatterns, 'ticketoutputpdf'))))


plugin_patterns = [path('', include((raw_plugin_patterns, 'plugins')))]

# Add storage URLs for file uploads
storage_patterns = [
    path('storage/', include('eventyay.storage.urls', namespace='storage')),
]

# Add live URLs for video/BBB features (CSS endpoints, etc.)
live_patterns = [
    path('', include(('eventyay.features.live.urls', 'live'))),
]

from .views import (
    AnonymousInviteRedirectView,
    VideoAdminRedirectView,
    VideoAssetView,
    VideoSPAView,
)

video_organizer_patterns = [
    re_path(
        r'^video/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/assets/(?P<path>.*)$',
        VideoAssetView.as_view(),
        name='video.organizer.assets',
    ),
    re_path(
        r'^video/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/(?P<path>[^?]*\.[a-zA-Z0-9._-]+)$',
        VideoAssetView.as_view(),
        name='video.organizer.assets.file',
    ),
    re_path(
        r'^video/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)(?:/(?P<subpath>.*))?$',
        VideoSPAView.as_view(is_organizer=True),
        name='video.organizer.spa',
    ),
]

unified_event_patterns = [
    path(
        '<orgslug:organizer>/<slug:event>/',
        include(
            [
                # Video patterns under {organizer}/{event}/video/
                # Match static assets with file extensions (js, css, png, etc.)
                re_path(r'^video/assets/(?P<path>.*)$', VideoAssetView.as_view(), name='video.assets'),
                re_path(
                    r'^video/(?P<path>[^?]*\.[a-zA-Z0-9._-]+)$',
                    VideoAssetView.as_view(),
                    name='video.assets.file',
                ),
                # Legacy organizer admin routes redirect to /video/event/{organizer}/{event}/...
                re_path(
                    r'^video/(?:admin|event)(?:/(?P<subpath>.*))?$',
                    VideoAdminRedirectView.as_view(),
                    name='video.admin.redirect',
                ),
                # Public attendee-facing video SPA app
                re_path(r'^video(?:/.*)?$', VideoSPAView.as_view(is_organizer=False), name='video.spa'),
                path('', include(('eventyay.agenda.urls', 'agenda'))),
                path('', include(('eventyay.cfp.urls', 'cfp'))),
            ]
        ),
    ),
]

# Anonymous room invite short token pattern (6 characters)
# The token uses characters: abcdefghijklmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ123456789
# (excludes visually confusing characters: l, o, I, O, 0)
anonymous_invite_patterns = [
    re_path(
        r'^(?P<token>[a-km-np-zA-HJ-NP-Z1-9]{6})/?$',
        AnonymousInviteRedirectView.as_view(),
        name='anonymous.invite.redirect',
    ),
]

urlpatterns = (
    common_patterns
    + storage_patterns
    + live_patterns
    + video_organizer_patterns
    # The plugins patterns must be before presale_patterns_main
    # to avoid misdetection of plugin prefixes and organizer/event slugs.
    # Anonymous invite short token redirects (before presale to avoid slug conflict)
    + anonymous_invite_patterns
    + plugin_patterns
    + presale_patterns_main
    + unified_event_patterns
)

handler404 = 'eventyay.base.views.errors.page_not_found'
handler500 = 'eventyay.base.views.errors.server_error'
