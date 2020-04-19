import pytest
from django.forms import ValidationError

from pretalx.common.forms.utils import validate_field_length


@pytest.mark.parametrize(
    "value,min_length,max_length,count_in,valid",
    (
        ("word word word", None, None, "chars", True),
        ("word word word", None, None, "words", True),
        ("word word word", 1, None, "chars", True),
        ("word word word", 1, None, "words", True),
        ("word word word", None, 300, "chars", True),
        ("word word word", None, 3, "words", True),
        ("word word word", 1, 300, "chars", True),
        ("word word word", 1, 3, "words", True),
        ("word word word", 100, None, "chars", False),
        ("word word word", 4, None, "words", False),
        ("word word word", None, 3, "chars", False),
        ("word word word", None, 2, "words", False),
        ("word word word", 10, 11, "chars", False),
        ("word word word", 2, 2, "words", False),
    ),
)
def test_validate_field_length(value, min_length, max_length, count_in, valid):
    if valid:
        assert (
            validate_field_length(
                value=value,
                min_length=min_length,
                max_length=max_length,
                count_in=count_in,
            )
            is None
        )
    else:
        with pytest.raises(ValidationError):
            validate_field_length(
                value=value,
                min_length=min_length,
                max_length=max_length,
                count_in=count_in,
            )
