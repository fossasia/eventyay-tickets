import logging
from smtplib import SMTPRecipientsRefused, SMTPSenderRefused
from typing import Any, Dict, Union

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.smtp import EmailBackend
from django.utils.translation import override
from i18nfield.strings import LazyI18nString
from inlinestyler.utils import inline_css

from pretalx.celery_app import app
from pretalx.event.models import Event
from pretalx.person.models import User

logger = logging.getLogger(__name__)


class CustomSMTPBackend(EmailBackend):
    def test(self, from_addr):
        try:
            self.open()
            self.connection.ehlo_or_helo_if_needed()
            self.connection.rcpt('test@example.org')
            (code, resp) = self.connection.mail(from_addr, [])
            if code != 250:
                logger.warning(
                    f'Error testing mail settings, code {code}, resp: {resp}'
                )
                raise SMTPSenderRefused(code, resp, from_addr)
            senderrs = {}
            (code, resp) = self.connection.rcpt('test@example.com')
            if code not in (250, 251):
                logger.warning(
                    f'Error testing mail settings, code {code}, resp: {resp}'
                )
                raise SMTPRecipientsRefused(senderrs)
        finally:
            self.close()


class TolerantDict(dict):
    def __missing__(self, key):
        """Don't fail when formatting strings with a dict with missing keys."""
        return key


class SendMailException(Exception):
    pass


def mail(
    user: User,
    subject: str,
    template: Union[str, LazyI18nString],
    context: Dict[str, Any] = None,
    event: Event = None,
    locale: str = None,
    headers: dict = None,
):
    from pretalx.mail.models import QueuedMail

    headers = headers or {}

    with override(locale):
        body = str(template)
        if context:
            body = body.format_map(TolerantDict(context))

        QueuedMail(
            event=event,
            to=user.email,
            subject=str(subject),
            text=body,
            reply_to=headers.get('reply-to'),
            bcc=headers.get('bcc'),
        ).send()


@app.task
def mail_send_task(
    to: str,
    subject: str,
    body: str,
    html: str,
    reply_to: str = None,
    event: int = None,
    cc: list = None,
    bcc: list = None,
    headers: dict = None,
):
    headers = headers or dict()
    if event:
        event = Event.objects.filter(id=event).first()
    if event:
        sender = event.settings.get('mail_from')
        if sender == 'noreply@example.org' or not sender:
            sender = settings.MAIL_FROM
        if reply_to:
            headers['reply-to'] = reply_to
        backend = event.get_mail_backend()
    else:
        sender = settings.MAIL_FROM
        backend = get_connection(fail_silently=False)

    email = EmailMultiAlternatives(
        subject, body, sender, to=to, cc=cc, bcc=bcc, headers=headers
    )

    if html is not None:
        email.attach_alternative(inline_css(html), 'text/html')

    try:
        backend.send_messages([email])
    except Exception:
        logger.exception('Error sending email')
        raise SendMailException('Failed to send an email to {}.'.format(to))
