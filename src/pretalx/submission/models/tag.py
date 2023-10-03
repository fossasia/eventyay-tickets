from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nTextField

from pretalx.common.mixins.models import PretalxModel
from pretalx.common.urls import EventUrls


class Tag(PretalxModel):
    event = models.ForeignKey(
        to="event.Event", on_delete=models.PROTECT, related_name="tags"
    )

    tag = models.CharField(max_length=50)
    description = I18nTextField(
        verbose_name=_("Description"),
        blank=True,
    )
    color = models.CharField(
        max_length=7,
        verbose_name=_("Color"),
        validators=[
            RegexValidator(r"#([0-9A-Fa-f]{3}){1,2}"),
        ],
    )
    public = models.BooleanField(
        default=False,
        verbose_name=_("Show tag publicly"),
        help_text=_(
            "Tags are currently only in use for organisers and reviewers. They will be visible publicly in a future release of pretalx."
        ),
    )

    class urls(EventUrls):
        base = edit = "{self.event.orga_urls.tags}{self.pk}/"
        delete = "{base}delete"

    def __str__(self) -> str:
        return str(self.tag)
