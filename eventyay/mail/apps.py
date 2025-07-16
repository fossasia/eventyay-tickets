from django.apps import AppConfig


class MailConfig(AppConfig):
    name = "eventyay.mail"

    def ready(self):
        from . import signals  # noqa
