from typing import Any

from django.template.defaultfilters import linebreaks

from django_markup.filter import MarkupFilter


class LinebreaksMarkupFilter(MarkupFilter):
    """
    Replaces line breaks in plain text with appropriate HTML; a single
    newline becomes an HTML line break (``<br />``) and a new line
    followed by a blank line becomes a paragraph break (``</p>``).
    """

    title = "Linebreaks"

    def render(
        self,
        text: str,
        **kwargs: Any,  # Unused argument
    ) -> str:
        return linebreaks(text, **kwargs)
