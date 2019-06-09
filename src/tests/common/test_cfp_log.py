import pytest
from django_scopes import scope

from pretalx.common.models.log import LOG_NAMES, ActivityLog


@pytest.fixture
def activity_log(event, submission):
    return ActivityLog(
        event=event, content_object=submission, action_type='pretalx.submission.create'
    )


@pytest.mark.django_db
def test_activity_log_display(activity_log):
    assert activity_log.display() == LOG_NAMES.get(activity_log.action_type)


@pytest.mark.django_db
def test_activity_log_display_incorrect(activity_log):
    activity_log.action_type = 'foo'
    assert activity_log.display() == 'foo'


@pytest.mark.django_db
def test_log_urls(activity_log, submission, choice_question, answer, mail_template):
    with scope(event=submission.event):
        assert activity_log.get_public_url() == submission.urls.public
        assert activity_log.get_orga_url() == submission.orga_urls.base

        activity_log.content_object = submission.event.cfp
        assert activity_log.get_public_url() == submission.event.cfp.urls.public
        assert activity_log.get_orga_url() == submission.event.cfp.urls.text

        activity_log.content_object = choice_question
        assert activity_log.get_public_url() == ''
        assert activity_log.get_orga_url() == choice_question.urls.base

        activity_log.content_object = choice_question.options.first()
        assert activity_log.get_orga_url() == choice_question.urls.base

        activity_log.content_object = answer
        assert activity_log.get_orga_url() == answer.submission.orga_urls.base
        answer.submission = None
        assert activity_log.get_orga_url() == answer.question.urls.base

        activity_log.content_object = mail_template
        assert activity_log.get_orga_url() == mail_template.urls.base
