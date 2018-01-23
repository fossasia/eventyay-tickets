import pytest

from pretalx.common.models.log import LOG_NAMES, ActivityLog


@pytest.fixture
def activity_log(event, submission):
    return ActivityLog(
        event=event, content_object=submission,
        action_type='pretalx.submission.create'
    )


@pytest.mark.django_db
def test_activity_log_display(activity_log):
    assert activity_log.display() == LOG_NAMES.get(activity_log.action_type)


@pytest.mark.django_db
def test_activity_log_display_incorrect(activity_log):
    activity_log.action_type = 'foo'
    assert activity_log.display() == 'foo'
