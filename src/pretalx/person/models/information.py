from django.db import models
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nCharField, I18nTextField

from pretalx.common.mixins.models import PretalxModel
from pretalx.common.phrases import phrases
from pretalx.common.urls import EventUrls
from pretalx.common.utils import path_with_hash


def resource_path(instance, filename):
    return f"{instance.event.slug}/speaker_information/{path_with_hash(filename)}"


class SpeakerInformation(PretalxModel):
    """Represents any information organisers want to show all or some
    submitters or speakers."""

    event = models.ForeignKey(
        to="event.Event", related_name="information", on_delete=models.CASCADE
    )
    target_group = models.CharField(
        choices=(
            ("submitters", _("All submitters")),
            ("accepted", _("All accepted speakers")),
            ("confirmed", _("Only confirmed speakers")),
        ),
        default="accepted",
        max_length=11,
    )
    limit_tracks = models.ManyToManyField(
        to="submission.Track",
        verbose_name=_("Limit to tracks"),
        blank=True,
        help_text=_("Leave empty to show this information to all tracks."),
    )
    limit_types = models.ManyToManyField(
        to="submission.SubmissionType",
        verbose_name=_("Limit to proposal types"),
        blank=True,
        help_text=_("Leave empty to show this information for all proposal types."),
    )
    title = I18nCharField(verbose_name=_("Subject"), max_length=200)
    text = I18nTextField(verbose_name=_("Text"), help_text=phrases.base.use_markdown)
    resource = models.FileField(
        verbose_name=_("File"),
        null=True,
        blank=True,
        help_text=_("Please try to keep your upload small, preferably below 16 MB."),
        upload_to=resource_path,
    )

    class orga_urls(EventUrls):
        base = edit = "{self.event.orga_urls.information}{self.pk}/"
        delete = "{base}delete"
