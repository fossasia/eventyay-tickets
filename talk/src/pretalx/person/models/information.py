from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from i18nfield.fields import I18nCharField, I18nTextField

from pretalx.common.models.mixins import PretalxModel
from pretalx.common.text.path import path_with_hash
from pretalx.common.text.phrases import phrases
from pretalx.common.urls import EventUrls


def resource_path(instance, filename):
    return path_with_hash(
        filename, base_path=f"{instance.event.slug}/speaker_information/"
    )


class SpeakerInformation(PretalxModel):
    """Represents any information organisers want to show all or some
    submitters or speakers."""

    event = models.ForeignKey(
        to="event.Event", related_name="information", on_delete=models.CASCADE
    )
    target_group = models.CharField(
        choices=(
            ("submitters", phrases.base.all_choices),
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
    title = I18nCharField(
        verbose_name=pgettext_lazy("email subject", "Subject"), max_length=200
    )
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
