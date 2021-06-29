from django.apps import AppConfig


class SubmissionConfig(AppConfig):
    name = "pretalx.submission"

    def ready(self):
        from . import exporters  # noqa
        from . import permissions  # noqa
        from . import signals  # noqa
