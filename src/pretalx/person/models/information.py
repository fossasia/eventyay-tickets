from django.db import models
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nCharField, I18nTextField

from pretalx.common.mixins import LogMixin


class SpeakerInformation(LogMixin, models.Model):
    event = models.ForeignKey(
        to='event.Event',
        related_name='information',
        on_delete=models.CASCADE,
    )
    include_submitters = models.BooleanField(
        verbose_name=_('Include all submitters'),
        help_text=_('Show to every submitter regardless of their submissions\' status'),
        default=False,
    )
    exclude_unconfirmed = models.BooleanField(
        verbose_name=_('Exclude unconfirmed speakers'),
        help_text=_('Show to speakers only once they have confirmed attendance'),
        default=False,
    )
    title = I18nCharField(
        verbose_name=_('Subject'),
        max_length=200,
    )
    text = I18nTextField(
        verbose_name=_('Text'),
        help_text=_('You can use markdown here.'),
    )
