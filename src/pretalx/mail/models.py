from django.db import models
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nCharField, I18nTextField


class MailTemplate(models.Model):
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
    log_address = models.EmailField(
        max_length=200,
        blank=True, null=True,
        verbose_name=_('Log address'),
        help_text=_('You can choose to receive one notification mail for every batch of mails sent from this template.')
    )
    bcc = models.CharField(
        max_length=1000,
        blank=True, null=True,
        verbose_name=_('BCC'),
        help_text=_('Enter comma separated addresses. Will receive a blind copy of every mail sent from this template. This may be a LOT!')
    )


class QueuedMail(models.Model):
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
