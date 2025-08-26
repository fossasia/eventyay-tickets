from django.conf import settings
from django.utils.functional import cached_property
from django.utils.log import AdminEmailHandler
from django.views.debug import ExceptionReporter


class SendMailException(Exception):
    pass


class SubmissionError(Exception):
    pass


class AuthenticationFailedError(Exception):
    pass


class VideoIntegrationError(Exception):
    pass


class PretalxExceptionReporter(ExceptionReporter):
    def get_traceback_text(self):  # pragma: no cover
        traceback_text = super().get_traceback_text()
        # Don't try to send fancy emails in dev
        if settings.DEBUG or not self.is_email:
            return traceback_text

        exception = self.exc_type.__name__ if getattr(self, 'exc_type', None) else 'Exception'
        exception_info = str(getattr(self, 'exc_value', '') or '')
        if exception_info:
            exception += f' ({exception_info})'
        location = ''
        frame = self.get_traceback_data().get('lastframe')
        if frame:
            location = f'{frame.get("filename")}:{frame.get("lineno")}'

        intro = f"""
You are receiving this email because an error occurred in your pretalx installation at {settings.SITE_URL}.
You can find the technical details below – if you find that the problem was not due to a configuration error,
please report this issue at

    https://github.com/pretalx/pretalx/issues/new/choose

The error was {exception} at {location}.
"""
        tldr = self.get_tldr()
        intro += self.get_extra_intro()
        return f'{tldr}\n{intro}\n\n{traceback_text}\n{tldr}\n'

    @cached_property
    def user(self):
        user = getattr(self.request, 'user', None)
        if not user:
            return ''
        if self.request.user.is_anonymous:
            return 'an anonymous user'
        return f'{self.request.user.name} <{self.request.user.email}>'

    def get_tldr(self):
        if not self.request:
            return ''
        tldr = f'tl;dr: An exception occurred when {self.user} accessed {self.request.path}'
        event = getattr(self.request, 'event', None)
        if event:
            tldr += f', an event page of {event.name}.'
        return tldr

    def get_extra_intro(self):
        if not self.request:
            return ''
        intro = '\nIt occurred when {self.user} accessed {self.request.path}.'
        event = getattr(self.request, 'event', None)
        if event:
            intro += f'\nThis page belongs to {event.name} <{event.orga_urls.base.full()}>.'
        return intro


class PretalxCeleryExceptionReporter(PretalxExceptionReporter):
    def __init__(self, *args, task_id=False, celery_args=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_id = task_id
        self.celery_args = celery_args

    def get_tldr(self):
        return f'tl;dr: An exception occurred in task {self.task_id}'

    def get_extra_intro(self):
        intro = ''
        if self.celery_args and len(self.celery_args) == 2:
            cargs, ckwargs = self.celery_args
            if cargs and hasattr(cargs, '__iter__'):
                cargs = ', '.join(cargs)
            if cargs:
                intro += f'\nTask args: {cargs}'
            if ckwargs:
                intro += f'\nTask kwargs: {ckwargs}'
        return intro


class PretalxAdminEmailHandler(AdminEmailHandler):
    reporter_class = PretalxExceptionReporter

    def emit(self, record):  # pragma: no cover
        request = getattr(record, 'request', None)
        if request and request.path == '/500':
            return
        return super().emit(record)
