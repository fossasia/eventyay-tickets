from django.apps import AppConfig


class MailConfig(AppConfig):
    name = "pretalx.mail"

    def ready(self):
        from . import signals  # noqa
