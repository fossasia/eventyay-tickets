from io import StringIO
from urllib.parse import quote

import qrcode
import qrcode.image.svg
from defusedcsv import csv
from defusedxml import ElementTree
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe

from pretalx.common.urls import EventUrls


class BaseExporter:
    """The base class for all data exporters."""

    def __init__(self, event):
        self.event = event

    def __str__(self):
        """The identifier may be used for callbacks and debugging."""
        return self.identifier

    @property
    def verbose_name(self) -> str:
        """A human-readable name for this exporter.

        This should be short but self-explaining. Good examples include
        'JSON' or 'Microsoft Excel'.
        """
        raise NotImplementedError()  # NOQA

    @property
    def identifier(self) -> str:
        """A short and unique identifier for this exporter.

        This should only contain lower-case letters and in most cases
        will be the same as your package name.
        """
        raise NotImplementedError()  # NOQA

    @cached_property
    def quoted_identifier(self) -> str:
        return quote(self.identifier)

    @property
    def public(self) -> bool:
        """Return True if the exported data should be publicly available once
        the event is public, False otherwise.

        If you need additional data to decide, you can instead implement the
        ``is_public(self, request, **kwargs)`` method, which overrides this
        property.
        """
        raise NotImplementedError()  # NOQA

    @property
    def show_public(self) -> bool:
        """This value determines if the exporter is listed among the public
        exporters on the schedule page. It defaults to the `public` property,
        but you can override it in order to hide public exports from the
        user-facing menu."""
        return self.public

    @property
    def cors(self) -> str:
        """If you want to let this exporter be accessed with JavaScript, set
        cors = '*' for all accessing domains, or supply a specific domain."""
        return None

    @property
    def show_qrcode(self) -> bool:
        """Return True if the link to the exporter should be shown as QR code,
        False (default) otherwise.

        Override the get_qr_code method to override the QR code itself.
        """
        return False

    @property
    def icon(self) -> str:
        """Return either a fa- string or some other symbol to accompany the
        exporter in displays."""
        raise NotImplementedError()  # NOQA

    @property
    def group(self) -> str:
        """Return either 'speaker' or 'submission' to indicate on which
        organiser export page to list this export.

        Invalid values default to 'submission', which is also where all
        schedule exports live.
        """
        return "submission"

    def render(self, request, **kwargs) -> tuple[str, str, str]:
        """Render the exported file and return a tuple consisting of a file
        name, a file type and file content."""
        raise NotImplementedError()  # NOQA

    class urls(EventUrls):
        """The base attribute of this class contains the relative URL where
        this exporter's data will be found, e.g. /event/schedule/export/my-
        export.ext Use ``exporter.urls.base.full()`` for the complete URL,
        taking into account the configured event URL, or HTML export URL."""

        base = "{self.event.urls.export}{self.quoted_identifier}"

    def get_qrcode(self):
        image = qrcode.make(
            self.urls.base.full(), image_factory=qrcode.image.svg.SvgPathFillImage
        )
        return mark_safe(ElementTree.tostring(image.get_image()).decode())


class CSVExporterMixin:
    def render(self, **kwargs):
        fieldnames, data = self.get_data()
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
        content = output.getvalue()
        return self.filename, "text/plain", content
