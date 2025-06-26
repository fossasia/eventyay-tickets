import os

from celery import Celery
from celery.exceptions import WorkerLostError
from celery.signals import task_failure
from django.core.mail import mail_admins

from pretalx.common.exceptions import PretalxCeleryExceptionReporter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pretalx.settings")

from django.conf import settings  # noqa

app = Celery("pretalx")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@task_failure.connect()
def send_exception_email(
    task_id, exception, args, kwargs, traceback, *_args, **_kwargs
):
    if settings.DEBUG or not settings.ADMINS:
        return
    if isinstance(exception, WorkerLostError):
        # We’re assuming that WorkerLostErrors are from restarting pretalx
        # which commonly sends SIGTERMs to celery workers
        return
    if settings.EMAIL_BACKEND == "django.core.mail.backends.locmem.EmailBackend":
        # Emails are going nowhere
        return

    reporter = PretalxCeleryExceptionReporter(
        request=None,
        exc_type=type(exception),
        exc_value=exception,
        tb=traceback,
        is_email=True,
        task_id=task_id,
        celery_args=(args, kwargs),
    )

    subject = f"[Django] ERROR (TASK): Internal Server Error: {task_id}"
    message = reporter.get_traceback_text()
    html_message = reporter.get_traceback_html()
    mail_admins(subject, message, fail_silently=True, html_message=html_message)
