import pytest
from django_scopes import scope

from pretalx.common.log_display import LOG_NAMES
from pretalx.common.models.log import ActivityLog


@pytest.fixture
def activity_log(event, submission):
    return ActivityLog(
        event=event, content_object=submission, action_type="pretalx.submission.create"
    )


@pytest.mark.django_db
def test_activity_log_display(activity_log):
    assert activity_log.display == LOG_NAMES.get(activity_log.action_type)


@pytest.mark.django_db
def test_activity_log_display_incorrect(activity_log):
    activity_log.action_type = "foo"
    assert activity_log.display == "foo"


@pytest.mark.django_db
def test_log_urls(
    activity_log, submission, choice_question, answer, mail_template, mail
):
    with scope(event=submission.event):
        assert submission.orga_urls.base in activity_log.display_object

        activity_log.content_object = submission.event.cfp
        del activity_log.display_object
        assert submission.event.cfp.urls.text in activity_log.display_object

        activity_log.content_object = choice_question
        del activity_log.display_object
        assert choice_question.urls.base in activity_log.display_object

        activity_log.content_object = choice_question.options.first()
        del activity_log.display_object
        assert choice_question.urls.base in activity_log.display_object

        activity_log.content_object = answer
        del activity_log.display_object
        assert answer.submission.orga_urls.base in activity_log.display_object
        answer.submission = None
        del activity_log.display_object
        assert answer.question.urls.base in activity_log.display_object

        activity_log.content_object = mail_template
        del activity_log.display_object
        assert mail_template.urls.base in activity_log.display_object

        activity_log.content_object = mail
        del activity_log.display_object
        assert mail.urls.base in activity_log.display_object
