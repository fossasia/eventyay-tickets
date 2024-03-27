from django.apps import AppConfig

from .database import *  # noqa


class PretixHelpersConfig(AppConfig):
    name = 'pretix.helpers'
    label = 'pretixhelpers'


