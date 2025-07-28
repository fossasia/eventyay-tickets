from django.apps import AppConfig


class PersonConfig(AppConfig):
    name = "eventyay.person"

    def ready(self):
        from . import signals  # noqa
        from . import tasks  # NOQA
