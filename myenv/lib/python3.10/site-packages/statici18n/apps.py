from django.apps import AppConfig


class StaticI18NConfig(AppConfig):
    name = "statici18n"

    def ready(self):
        from . import conf  # noqa
