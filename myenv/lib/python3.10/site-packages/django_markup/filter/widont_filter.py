from typing import Any

from django_markup.filter import MarkupFilter


class WidontMarkupFilter(MarkupFilter):
    title = "Widont"

    def render(
        self,
        text: str,
        **kwargs: Any,  # noqa: ARG002 Unused argument
    ) -> str:
        return "&nbsp;".join(text.strip().rsplit(" ", 1))
