from django.core.validators import RegexValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager
from i18nfield.fields import I18nCharField

from pretalx.common.mixins import LogMixin
from pretalx.common.urls import EventUrls


class Track(LogMixin, models.Model):
    """A track groups :class:`~pretalx.submission.models.submission.Submission`
    objects within an :class:`~pretalx.event.models.event.Event`, e.g. by
    topic.
    """
    event = models.ForeignKey(
        to='event.Event', on_delete=models.PROTECT, related_name='tracks'
    )
    name = I18nCharField(
        max_length=200,
        verbose_name=_('Name'),
    )
    color = models.CharField(
        max_length=7, verbose_name=_('Color'),
        validators=[
            RegexValidator(r'#([0-9A-Fa-f]{3}){1,2}'),
        ],
    )

    objects = ScopedManager(event='event')

    class urls(EventUrls):
        base = edit = '{self.event.cfp.urls.tracks}{self.pk}/'
        delete = '{base}delete'
        prefilled_cfp = '{self.event.cfp.urls.public}?track={self.slug}'

    def __str__(self) -> str:
        return str(self.name)

    @property
    def slug(self) -> str:
        """The slug makes tracks more readable in URLs.

        It consists of the ID, followed by a slugified (and, in lookups, optional) form of the track name."""
        return f'{self.id}-{slugify(self.name)}'
