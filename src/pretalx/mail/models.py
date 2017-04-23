from django.db import models
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nCharField, I18nTextField

from pretalx.common.mixins import LogMixin


class TolerantDict(dict):

    def __missing__(self, key):
        return key


class MailTemplate(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='mail_templates',
    )
    subject = I18nCharField(max_length=200)
    text = I18nTextField()
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
        help_text=_('Enter comma separated addresses. Will receive a blind copy of every mail sent from this template. This may be a LOT!')
    )

    def bulk_mail(self):
        # TODO: call to_mail
        pass

    def to_mail(self, user, event, locale=None, context=None, skip_queue=False):
        # TODO correct handling of locale. translation.activate()?
        context = TolerantDict(context or dict())
        mail = QueuedMail(
            event=self.event,
            to=user.email,
            reply_to=self.reply_to or event.email,
            bcc=self.bcc,
            subject=str(self.subject).format(**context),
            text=str(self.text).format(**context)
        )
        if skip_queue:
            mail.send()
        else:
            mail.save()


class QueuedMail(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='queued_mails',
    )
    to = models.CharField(max_length=1000)  # allow multiple recipients: several perople per talk
    reply_to = models.CharField(max_length=1000)
    cc = models.CharField(max_length=1000, null=True, blank=True)
    bcc = models.CharField(max_length=1000, null=True, blank=True)
    subject = models.CharField(max_length=200)  # Use non-i18n fields; this is the final actual to-be-sent version
    text = models.TextField()

    def send(self):
        from pretalx.common.mail import mail_send_task
        mail_send_task.apply_async(
            kwargs={
                'to': [self.to],
                'subject': self.subject,
                'body': self.text,
                'sender': self.reply_to,
                'event': self.event.pk,
            }
        )

        # TODO: log
        if self.pk:
            self.delete()
