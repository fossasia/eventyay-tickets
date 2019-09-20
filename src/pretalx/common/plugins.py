from django.apps import apps


def get_all_plugins(event=None):
    """Return the PretalxPluginMeta classes of all plugins found in the
    installed Django apps."""
    plugins = []
    for app in apps.get_app_configs():
        if hasattr(app, 'PretalxPluginMeta'):
            meta = app.PretalxPluginMeta
            meta.module = app.name
            meta.app = app

            if event and hasattr(app, 'is_available'):
                if not app.is_available(event):
                    continue

            plugins.append(meta)
    return sorted(
        plugins,
        key=lambda m: (
            0 if m.module.startswith('pretalx.') else 1,
            str(m.name).lower().replace('pretalx ', ''),
        ),
    )
