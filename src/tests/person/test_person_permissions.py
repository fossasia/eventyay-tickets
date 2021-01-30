import pytest
from django_scopes import scope

from pretalx.person.permissions import person_can_view_information


@pytest.mark.django_db
@pytest.mark.parametrize(
    "target_group,expected",
    (
        ("submitters", True),
        ("accepted", False),
        ("confirmed", False),
    ),
)
def test_can_view_information(information, submission, target_group, expected):
    with scope(event=submission.event):
        information.target_group = target_group
        information.save()
        assert (
            person_can_view_information(submission.speakers.first(), information)
            is expected
        )
