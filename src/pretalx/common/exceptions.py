from django.conf import settings
from django.utils.log import AdminEmailHandler
from django.views.debug import ExceptionReporter


class SendMailException(Exception):
    pass


class SubmissionError(Exception):
    pass


class PretalxExceptionReporter(ExceptionReporter):
    def get_traceback_text(self):  # pragma: no cover
        traceback_text = super().get_traceback_text()
        # Don't try to send fancy emails in dev, or when the exception comes from a task
        if settings.DEBUG or not self.is_email or not getattr(self, "request", None):
            return traceback_text
        exception = (
            self.exc_type.__name__ if getattr(self, "exc_type", None) else "Exception"
        )
        exception_info = str(getattr(self, "exc_value", "") or "")
        if exception_info:
            exception += f" ({exception_info})"
        location = ""
        frame = self.get_traceback_data().get("lastframe")
        if frame:
            location = f"{frame.get('filename')}:{frame.get('lineno')}"

        if self.request.user.is_anonymous:
            user = "an anonymous user"
        else:
            user = f"{self.request.user.name} <{self.request.user.email}>"

        intro = f"""
You are receiving this email because an error occurred in your pretalx installation at {settings.SITE_URL}.
You can find the technical details below – if you find that the problem was not due to a configuration error,
please report this issue at

    https://github.com/pretalx/pretalx/issues/new/choose

The error was {exception} at {location}.
It occurred when {user} accessed {self.request.path}.
"""
        tldr = f"tl;dr: An exception occurred when {user} accessed {self.request.path}"
        event = getattr(self.request, "event", None)
        if event:
            intro += (
                f"This page belongs to {event.name} <{event.orga_urls.base.full()}>."
            )
            tldr += f", an event page of {event.name}."
        traceback_text = f"{tldr}\n{intro}\n\n{traceback_text}\n{tldr}\n"
        return traceback_text


class PretalxAdminEmailHandler(AdminEmailHandler):
    reporter_class = PretalxExceptionReporter

    def emit(self, record):  # pragma: no cover
        request = getattr(record, "request", None)
        if request and request.path == "/500":
            return
        return super().emit(record)
