import json
import os

from django.apps import AppConfig
from django.core.files.base import ContentFile
from django.utils.translation import gettext, gettext_lazy as _

from pretix import __version__ as version


class BadgesApp(AppConfig):
    name = 'pretix.plugins.badges'
    verbose_name = _("Badges")

    class PretixPluginMeta:
        name = _("Badges")
        version = version
        category = "FEATURE"
        featured = True
        description = _("This plugin allows you to generate badges or name tags for your attendees.")

    def ready(self):
        from . import signals  # NOQA

    def installed(self, event):
        if not event.badge_layouts.exists():
            event.badge_layouts.create(
                name=gettext('Default'),
                default=True,
            )
            media_dir = os.path.join(os.path.dirname(__file__), 'media')
            templates_path = os.path.join(os.path.dirname(__file__), 'templates', 'pretixplugins', 'badgelayouts', 'templates.json')
            with open(templates_path, 'r') as file:
                templates = json.load(file)
            for template_name, template_data in templates.items():
                design_name = template_data['name']
                template_path = os.path.join(media_dir, f'{design_name}.pdf')
                if os.path.exists(templates_path):
                    with open(template_path, 'rb') as f:
                        content = f.read()
                    content_file = ContentFile(content, name=f'{design_name}.pdf')
                    event.badge_layouts.create(
                        name=gettext(design_name),
                        layout=template_data['layout'],
                        background=content_file
                    )


default_app_config = 'pretix.plugins.badges.BadgesApp'
