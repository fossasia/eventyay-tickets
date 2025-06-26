import pytest
from django_scopes import scope

from pretalx.orga.views.cards import _text


@pytest.mark.parametrize(
    "text,length,expected",
    (
        ("12345", 3, "12…"),
        ("12345", 5, "12345"),
    ),
)
def test_ellipsize(text, length, expected):
    assert _text(text, length) == expected


@pytest.mark.django_db
def test_orga_can_show_cards(orga_client, event, slot, other_slot):
    with scope(event=event):
        other_slot.submission.abstract = None
        other_slot.submission.notes = None
        other_slot.submission.save()
    response = orga_client.get(event.orga_urls.submission_cards)
    assert response.status_code == 200
