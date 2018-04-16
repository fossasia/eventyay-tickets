from django.apps import apps


def get_all_plugins():
    """Return the PretalxPluginMeta classes of all plugins found in the installed Django apps."""
    plugins = []
    for app in apps.get_app_configs():
        if hasattr(app, 'PretalxPluginMeta'):
            meta = app.PretalxPluginMeta
            meta.module = app.name
            meta.app = app
            plugins.append(meta)
    return plugins
