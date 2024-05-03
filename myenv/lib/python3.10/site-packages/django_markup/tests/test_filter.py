from __future__ import annotations

from pathlib import Path

import pytest
from django.test import TestCase

from django_markup.markup import UnregisteredFilterError, formatter

from . import markup_strings as s

FILES_DIR = Path(__file__).parent / "files"


class FormatterTestCase(TestCase):
    """
    Test the Formatter conversion done in Python of all shipped filters.
    """

    def read(self, filename: str) -> str:
        with (FILES_DIR / filename).open("r") as f:
            return f.read()

    def test_unregistered_filter_fails_loud(self) -> None:
        """
        Trying to call a unregistered filter will raise a ValueError.
        """
        pytest.raises(
            UnregisteredFilterError,
            formatter,
            "some text",
            filter_name="does-not-exist",
        )

    def test_none_filter(self) -> None:
        text, expected = s.NONE
        result = formatter(text, filter_name="none")
        assert result == expected

    def test_linebreaks_filter(self) -> None:
        text, expected = s.LINEBREAKS
        result = formatter(text, filter_name="linebreaks")
        assert result == expected

    def test_markdown_filter(self) -> None:
        text, expected = s.MARKDOWN
        result = formatter(text, filter_name="markdown")
        assert result == expected

    def test_markdown_filter_pre(self) -> None:
        text, expected = s.MARKDOWN_PRE
        result = formatter(text, filter_name="markdown")
        assert result == expected

    def test_markdown_safemode_enabled_by_default(self) -> None:
        """Safe mode is enabled by default."""
        text, expected = s.MARKDOWN_JS_LINK
        result = formatter(text, filter_name="markdown")
        assert result == expected

    def test_textile_filter(self) -> None:
        text, expected = s.TEXTILE
        result = formatter(text, filter_name="textile")
        assert result == expected

    def test_rst_filter(self) -> None:
        text, expected = s.RST
        result = formatter(text, filter_name="restructuredtext")
        assert result == expected

    def test_rst_header_levels(self) -> None:
        """
        Make sure the rST filter fetches the entire document rather just the
        document fragment.

        :see: https://github.com/bartTC/django-markup/issues/14
        """
        text = self.read("rst_header.txt")
        expected = self.read("rst_header_expected.txt")
        result = formatter(text, filter_name="restructuredtext")
        assert result == expected

    def test_rst_with_pygments(self) -> None:
        """
        Having Pygments installed will automatically provide a ``.. code-block``
        directive in reStructredText to highlight code snippets.
        """
        text = self.read("rst_with_pygments.txt")
        expected = self.read("rst_with_pygments_expected.txt")
        result = formatter(text, filter_name="restructuredtext")

        assert result == expected

    def test_rst_raw_default(self) -> None:
        """Raw file inclusion is disabled by default."""
        text = self.read("rst_raw.txt")
        result = formatter(text, filter_name="restructuredtext")
        assert "Other text" in result
        assert "<script>" not in result

    def test_rst_include_default(self) -> None:
        """File inclusion is disabled by default."""
        # Build up dynamically in order to build absolute path
        text = (
            f".. include:: {FILES_DIR / 'rst_header.txt'!s}"  # noqa: ISC003
            + "\n\nOther text\n"
        )
        result = formatter(text, filter_name="restructuredtext")
        assert "Other text" in result
        assert "Header 1" not in result

    def test_creole_filter(self) -> None:
        text, expected = s.CREOLE
        result = formatter(text, filter_name="creole")
        assert result == expected

    def test_smartypants_filter(self) -> None:
        text, expected = s.SMARTYPANTS
        result = formatter(text, filter_name="smartypants")
        assert result == expected

    def test_widont_filter(self) -> None:
        text, expected = s.WIDONT
        result = formatter(text, filter_name="widont")
        assert result == expected
