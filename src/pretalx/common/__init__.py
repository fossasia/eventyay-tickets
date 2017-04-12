from django.apps import AppConfig


class CommonConfig(AppConfig):
    label = 'pretalxcommon'
    name = 'pretalx.common'


try:
    import pretalx.celery_app as celery  # NOQA
except ImportError:
    pass
