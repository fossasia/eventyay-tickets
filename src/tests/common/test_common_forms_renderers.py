import pytest

from pretalx.common.forms.renderers import render_label


@pytest.mark.parametrize(
    "label_class,label_title,expected",
    (
        (None, None, '<label for="forrr">content</label>'),
        ("clllass", None, '<label class="clllass" for="forrr">content</label>'),
        (None, "tiiitle", '<label for="forrr" title="tiiitle">content</label>'),
        (
            "clllass",
            "tiiitle",
            '<label class="clllass" for="forrr" title="tiiitle">content</label>',
        ),
    ),
)
def test_render(label_class, label_title, expected):
    assert (
        render_label(
            "content",
            label_for="forrr",
            label_class=label_class,
            label_title=label_title,
        )
        == expected
    )
