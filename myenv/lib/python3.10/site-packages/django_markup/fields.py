from __future__ import annotations

from typing import Any

from django.db.models.fields import CharField
from django.utils.translation import gettext_lazy

from django_markup.markup import MarkupFormatter, UnregisteredFilterError, formatter


class MarkupField(CharField):
    """
    A CharField that holds the markup name for the row. In the admin it's
    displayed as a ChoiceField.
    """

    def __init__(
        self,
        default: bool = False,
        formatter: MarkupFormatter = formatter,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        # Check that the default value is a valid filter
        if default:
            if default not in formatter.filter_list:
                msg = (
                    f"'{default}' is not a registered markup filter. "
                    f"Registered filters are: {formatter.registered_filter_names}."
                )
                raise UnregisteredFilterError(msg)
            kwargs.setdefault("default", default)

        kwargs.setdefault("max_length", 255)
        kwargs.setdefault("choices", formatter.choices())
        kwargs.setdefault("verbose_name", gettext_lazy("markup"))
        CharField.__init__(self, *args, **kwargs)
