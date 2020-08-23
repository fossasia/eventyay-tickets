import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "venueless.settings")
app = Celery("venueless")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
