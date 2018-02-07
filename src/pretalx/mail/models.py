from copy import deepcopy

import bleach
import markdown
from django.db import models
from django.template.loader import get_template
from django.utils.timezone import now
from django.utils.translation import override, ugettext_lazy as _
from i18nfield.fields import I18nCharField, I18nTextField

from pretalx.common.mail import SendMailException
from pretalx.common.mixins import LogMixin
from pretalx.common.urls import EventUrls


class TolerantDict(dict):

    def __missing__(self, key):
        return key


class MailTemplate(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='mail_templates',
    )
    subject = I18nCharField(
        max_length=200,
        verbose_name=_('Subject'),
    )
    text = I18nTextField(
        verbose_name=_('Text'),
    )
    reply_to = models.EmailField(
        max_length=200,
        blank=True, null=True,
        verbose_name=_('Reply-To'),
        help_text=_('Change the Reply-To address if you do not want to use the default orga address'),
    )
    bcc = models.CharField(
        max_length=1000,
        blank=True, null=True,
        verbose_name=_('BCC'),
        help_text=_('Enter comma separated addresses. Will receive a blind copy of every mail sent from this template. This may be a LOT!'),
    )

    class urls(EventUrls):
        base = edit = '{self.event.orga_urls.mail_templates}/{self.pk}'
        delete = '{base}/delete'

    def __str__(self):
        return f'MailTemplate(event={self.event.slug}, subject={self.subject})'

    def to_mail(self, user, event, locale=None, context=None, skip_queue=False):
        address = user.email if hasattr(user, 'email') else user
        with override(locale):
            context = context or dict()
            try:
                subject = str(self.subject).format(**context)
                text = str(self.text).format(**context)
            except KeyError as e:
                raise SendMailException(f'Experienced KeyError when rendering Text: {str(e)}')

            mail = QueuedMail(
                event=self.event,
                to=address,
                reply_to=self.reply_to or event.email,
                bcc=self.bcc,
                subject=subject,
                text=text,
            )
            if skip_queue:
                mail.send()
            else:
                mail.save()
        return mail


class QueuedMail(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='queued_mails',
    )
    to = models.CharField(
        max_length=1000,
        verbose_name=_('To'),
        help_text=_('One email address or several addresses separated by commas.'),
    )
    reply_to = models.CharField(
        max_length=1000,
        null=True, blank=True,
        verbose_name=_('Reply-To'),
        help_text=_('By default, the orga address is used as Reply-To.'),
    )
    cc = models.CharField(
        max_length=1000,
        null=True, blank=True,
        verbose_name=_('CC'),
        help_text=_('One email address or several addresses separated by commas.'),
    )
    bcc = models.CharField(
        max_length=1000,
        null=True, blank=True,
        verbose_name=_('BCC'),
        help_text=_('One email address or several addresses separated by commas.'),
    )
    subject = models.CharField(
        max_length=200,
        verbose_name=_('Subject'),
    )
    text = models.TextField(verbose_name=_('Text'))
    sent = models.DateTimeField(null=True, blank=True, verbose_name=_('Sent at'))

    class urls(EventUrls):
        base = edit = '{self.event.orga_urls.mail}/{self.pk}'
        delete = '{base}/delete'
        send = '{base}/send'
        copy = '{base}/copy'

    def __str__(self):
        sent = self.sent.isoformat() if self.sent else None
        return f'MailTemplate(event={self.event.slug}, to={self.to}, subject={self.subject}, sent={sent})'

    @classmethod
    def text_to_html(cls, text, event=None):
        body_md = bleach.linkify(bleach.clean(markdown.markdown(text), tags=bleach.ALLOWED_TAGS + [
            'p', 'pre'
        ]))
        html_context = {
            'body': body_md,
            'event': event,
            'color': (event.primary_color if event else '') or '#1c4a3b',
        }
        return get_template('mail/mailwrapper.html').render(html_context)

    def send(self):
        if self.sent:
            raise Exception('This mail has been sent already. It cannot be sent again.')

        body_html = self.text_to_html(self.text)
        from pretalx.common.mail import mail_send_task
        mail_send_task.apply_async(
            kwargs={
                'to': self.to.split(','),
                'subject': self.subject,
                'body': self.text,
                'html': body_html,
                'sender': self.reply_to,
                'event': self.event.pk,
                'cc': (self.cc or '').split(','),
                'bcc': (self.bcc or '').split(','),
            }
        )

        self.sent = now()
        if self.pk:
            self.save()

    def copy_to_draft(self):
        new_mail = deepcopy(self)
        new_mail.pk = None
        new_mail.sent = None
        new_mail.save()
        return new_mail
