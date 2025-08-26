from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nTextField

from eventyay.common.urls import EventUrls
from eventyay.talk_rules.person import is_reviewer
from eventyay.talk_rules.submission import (
    orga_can_change_submissions,
    orga_can_view_submissions,
    reviewer_can_change_tags,
    reviewer_can_create_tags,
)

from .mixins import PretalxModel


class Tag(PretalxModel):
    event = models.ForeignKey(to='Event', on_delete=models.PROTECT, related_name='tags')

    tag = models.CharField(max_length=50)
    description = I18nTextField(
        verbose_name=_('Description'),
        blank=True,
    )
    color = models.CharField(
        max_length=7,
        verbose_name=_('Color'),
        validators=[
            RegexValidator('#([0-9A-Fa-f]{3}){1,2}'),
        ],
    )
    is_public = models.BooleanField(
        default=False,
        verbose_name=_('Show tag publicly'),
        help_text=_(
            'Tags are currently only in use for organisers and reviewers. '
            'They will be visible publicly in a future release of pretalx.'
        ),
    )

    log_prefix = 'pretalx.tag'

    class Meta:
        rules_permissions = {
            'list': orga_can_view_submissions,
            'view': orga_can_view_submissions,
            'create': orga_can_change_submissions | (is_reviewer & reviewer_can_create_tags),
            'update': orga_can_change_submissions | (is_reviewer & reviewer_can_change_tags),
            'delete': orga_can_change_submissions | (is_reviewer & reviewer_can_change_tags),
        }
        unique_together = (('event', 'tag'),)

    class urls(EventUrls):
        base = edit = '{self.event.orga_urls.tags}{self.pk}/'
        delete = '{base}delete/'

    def __str__(self) -> str:
        return str(self.tag)

    @property
    def log_parent(self):
        return self.event
