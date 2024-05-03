from typing import Any, ClassVar

from django_markup.filter import MarkupFilter


class RstMarkupFilter(MarkupFilter):
    """
    Converts a reStructuredText string to HTML. If the pygments library is
     installed, you can use a special `sourcecode` directive to highlight
    portions of your text. Example:

    .. sourcecode: python

        def foo():
            return 'foo'
    """

    title = "reStructuredText"
    rst_part_name = "html_body"
    kwargs: ClassVar = {
        "settings_overrides": {
            "raw_enabled": False,
            "file_insertion_enabled": False,
        },
    }

    def render(
        self,
        text: str,
        **kwargs: Any,  # Unused argument
    ) -> str:
        if kwargs:
            self.kwargs.update(kwargs)
        from docutils import core

        publish_args = {"source": text, "writer_name": "html4css1"}
        publish_args.update(**self.kwargs)
        parts = core.publish_parts(**publish_args)
        return parts[self.rst_part_name]
