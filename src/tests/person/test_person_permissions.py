import pytest
from django_scopes import scope

from pretalx.person.permissions import person_can_view_information


@pytest.mark.django_db
@pytest.mark.parametrize(
    "include_submitters,exclude_unconfirmed,expected",
    (
        (True, True, True),
        (False, True, False),
        (False, False, False),
    ),
)
def test_can_view_information(
    information, submission, include_submitters, exclude_unconfirmed, expected
):
    with scope(event=submission.event):
        information.include_submitters = include_submitters
        information.exclude_unconfirmed = exclude_unconfirmed
        information.save()
        assert (
            person_can_view_information(submission.speakers.first(), information)
            is expected
        )
