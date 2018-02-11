from django.apps import AppConfig


class MailConfig(AppConfig):
    name = 'pretalx.mail'


default_app_config = 'pretalx.mail.MailConfig'
