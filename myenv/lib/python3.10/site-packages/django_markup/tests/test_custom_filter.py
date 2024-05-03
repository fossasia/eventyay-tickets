from __future__ import annotations

from typing import Any

import pytest
from django.test import TestCase

from django_markup.filter import MarkupFilter
from django_markup.markup import UnregisteredFilterError, formatter


class UppercaseMarkupFilter(MarkupFilter):
    """
    Custom filter that makes all the text uppercase.
    """

    title = "UppercaseFilter"

    def render(
        self,
        text: str,
        **kwargs: Any,  # noqa: ARG002 Unused argument
    ) -> str:
        return text.upper()


class LowercaseMarkupFilter(MarkupFilter):
    """
    Custom filter that makes all the text lowercase.
    """

    title = "LowercaseFilter"

    def render(
        self,
        text: str,
        **kwargs: Any,  # noqa: ARG002 Unused argument
    ) -> str:
        return text.lower()


class CustomMarkupFilterTestCase(TestCase):
    """
    Test the registration/unregistration of a custom filter.
    """

    def test_register_filter(self) -> None:
        """
        Register the filter, and its wildly available.
        """
        formatter.register("uppercase", UppercaseMarkupFilter)

        # It's ready to be called
        result = formatter("This is some text", filter_name="uppercase")
        assert result == "THIS IS SOME TEXT"

    def test_update_filter(self) -> None:
        """
        You can update an existing filter, but keep the name.
        """
        formatter.update("uppercase", LowercaseMarkupFilter)

        # Despite its key name is still 'uppercase' we actually call the
        # LowercaseFilter.
        result = formatter("This Is Some Text", filter_name="uppercase")
        assert result == "this is some text"

    def test_unregister_filter(self) -> None:
        # Unregistering a filter that does not exist is simply ignored
        formatter.unregister("does-not-exist")

        # Unregistering an registered filter, and it no longer works and will
        # raise a ValueError.
        formatter.register("uppercase", UppercaseMarkupFilter)
        formatter.unregister("uppercase")

        pytest.raises(
            UnregisteredFilterError,
            formatter,
            "This is some text",
            filter_name="uppercase",
        )

    def test_fallback_filter(self) -> None:
        """
        You can call the formatter without a `filter_name` as long as a
        `MARKUP_FILTER_FALLBACK` setting is set.
        """
        pytest.raises(
            UnregisteredFilterError,
            formatter,
            "This is some text",
            filter_name=None,
        )

        formatter.register("uppercase", UppercaseMarkupFilter)

        with self.settings(MARKUP_FILTER_FALLBACK="uppercase"):
            result = formatter("This is some text", filter_name=None)
            assert result == "THIS IS SOME TEXT"
