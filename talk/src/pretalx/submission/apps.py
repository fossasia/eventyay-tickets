from django.apps import AppConfig


class SubmissionConfig(AppConfig):
    name = "pretalx.submission"

    def ready(self):
        from . import exporters  # noqa
        from . import rules  # noqa
        from . import signals  # noqa
        from .phrases import SubmissionPhrases  # noqa
