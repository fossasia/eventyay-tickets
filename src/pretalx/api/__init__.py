from django.apps import AppConfig


class APIConfig(AppConfig):
    name = 'pretalx.api'


default_app_config = 'pretalx.api.APIConfig'
