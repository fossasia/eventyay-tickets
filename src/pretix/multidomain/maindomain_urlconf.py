import importlib.util

from django.apps import apps
from django.urls import include, path
from django.views.generic import TemplateView

from pretix.multidomain.plugin_handler import plugin_event_urls
from pretix.presale.urls import (
    event_patterns, locale_patterns, organizer_patterns,
)
from pretix.urls import common_patterns

presale_patterns_main = [
    path('', include((locale_patterns + [
        path('<str:organizer>/', include(organizer_patterns)),
        path('<str:organizer>/<str:event>/', include(event_patterns)),
        path('', TemplateView.as_view(template_name='pretixpresale/index.html'), name="index")
    ], 'presale')))
]

raw_plugin_patterns = []
for app in apps.get_app_configs():
    if hasattr(app, 'PretixPluginMeta'):
        if importlib.util.find_spec(app.name + '.urls'):
            urlmod = importlib.import_module(app.name + '.urls')
            single_plugin_patterns = []
            if hasattr(urlmod, 'urlpatterns'):
                single_plugin_patterns += urlmod.urlpatterns
            if hasattr(urlmod, 'event_patterns'):
                patterns = plugin_event_urls(urlmod.event_patterns, plugin=app.name)
                single_plugin_patterns.append(path('<str:organizer>/<str:event>/',
                                                  include(patterns)))
            if hasattr(urlmod, 'organizer_patterns'):
                patterns = urlmod.organizer_patterns
                single_plugin_patterns.append(path('<str:organizer>/',
                                                  include(patterns)))
            raw_plugin_patterns.append(
                path('', include((single_plugin_patterns, app.label)))
            )

plugin_patterns = [
    path('', include((raw_plugin_patterns, 'plugins')))
]

# The presale namespace comes last, because it contains a wildcard catch
urlpatterns = common_patterns + plugin_patterns + presale_patterns_main

handler404 = 'pretix.base.views.errors.page_not_found'
handler500 = 'pretix.base.views.errors.server_error'
