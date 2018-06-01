from typing import Tuple


class BaseExporter:
    """The base class for all data exporters."""

    def __init__(self, event):
        self.event = event

    def __str__(self):
        """The identifier may be used for callbacks and debugging."""
        return self.identifier

    @property
    def verbose_name(self) -> str:
        """
        A human-readable name for this exporter.

        This should be short but self-explaining. Good examples include 'JSON' or 'Microsoft Excel'.
        """
        raise NotImplementedError()  # NOQA

    @property
    def identifier(self) -> str:
        """
        A short and unique identifier for this exporter.

        This should only contain lower-case letters and in most
        cases will be the same as your package name.
        """
        raise NotImplementedError()  # NOQA

    @property
    def public(self) -> str:
        """Return True if the exported data should be publicly available once the event is public, False otherwise."""
        raise NotImplementedError()  # NOQA

    @property
    def icon(self) -> str:
        """Return either a fa- string or some other symbol to accompany the exporter in displays."""
        raise NotImplementedError()  # NOQA

    def render(self, **kwargs) -> Tuple[str, str, str]:
        """Render the exported file and return a tuple consisting of a file name, a file type and file content."""
        raise NotImplementedError()  # NOQA
