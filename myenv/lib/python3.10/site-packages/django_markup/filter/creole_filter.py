from typing import Any

from django_markup.filter import MarkupFilter


class CreoleMarkupFilter(MarkupFilter):
    title = "Creole (Wiki Syntax)"

    def render(
        self,
        text: str,
        **kwargs: Any,  # noqa: ARG002 Unused argument
    ) -> str:
        from creole import creole2html

        return creole2html(text)
