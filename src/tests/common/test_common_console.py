import pytest

from pretalx.common.console import get_separator, print_line


@pytest.mark.parametrize(
    "args,expected",
    (
        (
            (False, True, True, False),
            "┬",
        ),
        (
            (True, False, False, True),
            "┴",
        ),
        (
            (False, False, True, True),
            "┤",
        ),
        (
            (True, True, False, False),
            "├",
        ),
        (
            (False, True, False, True),
            "┼",
        ),
        (
            (True, False, True, False),
            "┼",
        ),
        (
            (True, True, True, True),
            "┼",
        ),
        (
            (False, True, True, True),
            "┼",
        ),
        (
            (True, False, True, True),
            "┼",
        ),
        (
            (True, True, False, True),
            "┼",
        ),
        (
            (True, True, True, False),
            "┼",
        ),
    ),
)
def test_get_separatro(args, expected):
    assert get_separator(*args) == expected


@pytest.mark.parametrize("box", (True, False))
@pytest.mark.parametrize("bold", (True, False))
@pytest.mark.parametrize("color", (None, "red"))
@pytest.mark.parametrize("size", (None, 2))
def test_print_line_does_not_barf(box, bold, color, size):
    print_line("Test", box=box, bold=bold, color=color, size=size)
