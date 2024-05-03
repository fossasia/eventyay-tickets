from __future__ import annotations

from django.template.loader import render_to_string
from django.test import TestCase

from django_markup.templatetags.markup_tags import apply_markup

from . import markup_strings as s


class PythonTemplateTagTestCase(TestCase):
    """
    Test the Templatetag conversion directly, without template rendering.

    No need to test all filters here, since their low level routines are
    covered in `test_filter`.
    """

    def test_none_filter(self) -> None:
        text, expected = s.NONE
        result = apply_markup(text, "none")
        assert result == expected

    def test_markdown_filter(self) -> None:
        text, expected = s.MARKDOWN
        result = apply_markup(text, "markdown")
        assert result == expected


class TemplateTagTestCase(TestCase):
    """
    Test the proper markup conversion using the template tag in a template itself.
    """

    def test_markdown_filter_with_templatetag(self) -> None:
        """
        Test usage as a template tag:

            {{ "some text"|apply_markup:"markdown" }}
        """
        text, expected = s.MARKDOWN
        result = render_to_string(
            "test_templatetag.html",
            {"text": text, "filter": "markdown"},
        )

        # Strip leading and trailing whitespace from the rendered HTL
        result = result.strip()

        assert result == expected

    def test_markdown_filter_with_templatetag_in_django_filterwrapper(
        self,
    ) -> None:
        """
        Test usage using Django's filter tag:

            {% filter apply_markup:"markdown" %}
                some text
            {% endfilter %}
        """
        text, expected = s.MARKDOWN
        result = render_to_string(
            "test_templatetag_filterwrapper.html",
            {"text": text, "filter": "markdown"},
        )

        # Strip leading and trailing whitespace from the rendered HTL
        result = result.strip()

        assert result == expected
