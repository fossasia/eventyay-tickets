from contextlib import suppress
from pathlib import Path

from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager

from pretalx.common.mixins.models import PretalxModel
from pretalx.common.urls import get_base_url
from pretalx.common.utils import path_with_hash


def resource_path(instance, filename):
    return f"{instance.submission.event.slug}/submissions/{instance.submission.code}/resources/{path_with_hash(filename)}"


class Resource(PretalxModel):
    """Resources are file uploads belonging to a :class:`~pretalx.submission.models.submission.Submission`."""

    submission = models.ForeignKey(
        to="submission.Submission", related_name="resources", on_delete=models.PROTECT
    )
    resource = models.FileField(
        verbose_name=_("File"),
        upload_to=resource_path,
        null=True,
        blank=True,
    )
    link = models.URLField(max_length=400, verbose_name=_("URL"), null=True, blank=True)
    description = models.CharField(
        null=True, blank=True, max_length=1000, verbose_name=_("Description")
    )

    objects = ScopedManager(event="submission__event")

    def __str__(self):
        """Help when debugging."""
        return f"Resource(event={self.submission.event.slug}, submission={self.submission.title})"

    @cached_property
    def url(self):
        if self.link:
            return self.link
        with suppress(ValueError):
            url = getattr(self.resource, "url", None)
            if url:
                base_url = get_base_url(self.submission.event)
                return base_url + url

    @cached_property
    def filename(self):
        with suppress(ValueError):
            if self.resource:
                return Path(self.resource.name).name
