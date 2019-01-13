from django.apps import AppConfig


class PersonConfig(AppConfig):
    name = 'pretalx.person'

    def ready(self):
        from . import signals  # noqa


default_app_config = 'pretalx.person.PersonConfig'
