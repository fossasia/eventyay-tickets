from typing import Any

from django_markup.filter import MarkupFilter


class SmartyPantsMarkupFilter(MarkupFilter):
    title = "SmartyPants"

    def render(
        self,
        text: str,
        **kwargs: Any,  # Unused argument
    ) -> str:
        from smartypants import smartypants

        return smartypants(text, **kwargs)
