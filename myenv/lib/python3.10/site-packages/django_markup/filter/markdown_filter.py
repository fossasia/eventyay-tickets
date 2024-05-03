from typing import Any, ClassVar

from django_markup.filter import MarkupFilter


class MarkdownMarkupFilter(MarkupFilter):
    """
    Applies Markdown conversion to a string, and returns the HTML.
    """

    title = "Markdown"
    kwargs: ClassVar = {"safe_mode": True}

    def render(
        self,
        text: str,
        **kwargs: Any,  # Unused argument
    ) -> str:
        if kwargs:
            self.kwargs.update(kwargs)

        from markdown import markdown

        text = markdown(text, **self.kwargs)

        # Markdown's safe_mode is deprecated. We replace it with Bleach
        # to keep it backwards compatible.
        # Https://python-markdown.github.io/change_log/release-2.6/#safe_mode-deprecated
        if self.kwargs.get("safe_mode") is True:
            from bleach import clean

            # fmt: off
            markdown_tags = [
                "h1", "h2", "h3", "h4", "h5", "h6",
                "b", "i", "strong", "em", "tt",
                "p", "br",
                "span", "div", "blockquote", "pre", "code", "hr",
                "ul", "ol", "li", "dd", "dt",
                "img",
                "a",
                "sub", "sup",
            ]

            markdown_attrs = {
                "*": ["id"],
                "img": ["src", "alt", "title"],
                "a": ["href", "alt", "title"],
            }
            # fmt: on

            text = clean(text, markdown_tags, markdown_attrs)

        return text
