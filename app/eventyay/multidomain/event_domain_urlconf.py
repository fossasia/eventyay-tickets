import importlib.util

from django.apps import apps
from django.urls import include
from django.urls import re_path as url

from eventyay.config.urls import common_patterns
from eventyay.multidomain.plugin_handler import plugin_event_urls
from eventyay.presale.urls import event_patterns, locale_patterns


presale_patterns = [
    url(
        r'',
        include(
            (
                locale_patterns
                + [
                    url(r'', include(event_patterns)),
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
            if hasattr(urlmod, 'event_patterns'):
                patterns = plugin_event_urls(urlmod.event_patterns, plugin=app.name)
                raw_plugin_patterns.append(url(r'', include((patterns, app.label))))

plugin_patterns = [url(r'', include((raw_plugin_patterns, 'plugins')))]

# The presale namespace comes last, because it contains a wildcard catch
urlpatterns = common_patterns + plugin_patterns + presale_patterns

handler404 = 'pretix.base.views.errors.page_not_found'
handler500 = 'pretix.base.views.errors.server_error'
