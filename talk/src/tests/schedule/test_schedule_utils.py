import pytest
from django_scopes import scope

from pretalx.schedule.notifications import (
    get_current_notifications,
    get_full_notifications,
)
from pretalx.schedule.utils import guess_schedule_version


@pytest.mark.django_db
@pytest.mark.parametrize(
    "previous,suggestion",
    (
        (None, "0.1"),
        ("0.1", "0.2"),
        ("0,2", "0,3"),
        ("0-3", "0-4"),
        ("0_4", "0_5"),
        ("1.0.1", "1.0.2"),
        ("Nichtnumerisch", ""),
        ("1.someting", ""),
        ("something.1", "something.2"),
    ),
)
def test_schedule_version_guessing(event, previous, suggestion):
    with scope(event=event):
        if previous:
            event.release_schedule(previous)
        assert guess_schedule_version(event) == suggestion


@pytest.mark.django_db
def test_schedule_notification_retrieval(event, slot):
    def assert_result_is_same(result, expected):
        """QuerySet comparison is magic"""
        assert list(result["create"]) == list(expected["create"])
        assert list(result["update"]) == list(expected["update"])

    with scope(event=event):
        speaker = slot.submission.speakers.first()
        expected = {
            "create": event.current_schedule.talks.filter(submission=slot.submission),
            "update": [],
        }
        assert_result_is_same(get_current_notifications(speaker, event), expected)
        assert_result_is_same(get_full_notifications(speaker, event), expected)

        event.wip_schedule.freeze("0.1test")

        expected["create"] = event.current_schedule.talks.filter(
            submission=slot.submission
        )
        assert get_current_notifications(speaker, event) == {"create": [], "update": []}
        assert_result_is_same(get_full_notifications(speaker, event), expected)
