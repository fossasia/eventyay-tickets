from django.apps import AppConfig


class SubmissionConfig(AppConfig):
    name = 'pretalx.submission'

    def ready(self):
        from . import permissions  # noqa
        from . import signals  # noqa


default_app_config = 'pretalx.submission.SubmissionConfig'
