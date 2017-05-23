import pytest

from pretalx.submission.models import SubmissionError, SubmissionStates


@pytest.mark.parametrize('state', (
    SubmissionStates.SUBMITTED,
    SubmissionStates.REJECTED,
))
@pytest.mark.django_db
def test_accept_success(submission, state):
    submission.state = state
    submission.save()
    count = submission.logged_actions().count()

    submission.accept()

    assert submission.state == SubmissionStates.ACCEPTED
    assert submission.logged_actions().count() == (count + 1)
    assert submission.event.queued_mails.count() == 1
    assert submission.event.wip_schedule.talks.count() == 1


@pytest.mark.parametrize('state', (
    SubmissionStates.ACCEPTED,
    SubmissionStates.CONFIRMED,
    SubmissionStates.CANCELED,
    SubmissionStates.WITHDRAWN,
))
@pytest.mark.parametrize('force', (True, False))
@pytest.mark.django_db
def test_accept_fail(submission, state, force):
    submission.state = state
    submission.save()
    count = submission.logged_actions().count()

    if force:
        submission.accept(force=force)

        assert submission.state == SubmissionStates.ACCEPTED
        assert submission.logged_actions().count() == (count + 1)
        assert submission.event.queued_mails.count() == 1
        assert submission.event.wip_schedule.talks.count() == 1

    else:
        with pytest.raises(SubmissionError):
            submission.accept(force=force)
        assert submission.state == state
        assert submission.event.queued_mails.count() == 0
        assert submission.event.wip_schedule.talks.count() == 0


@pytest.mark.parametrize('state', (
    SubmissionStates.SUBMITTED,
    SubmissionStates.REJECTED,
    SubmissionStates.ACCEPTED,
    SubmissionStates.CONFIRMED,
    SubmissionStates.CANCELED,
    SubmissionStates.WITHDRAWN,
))
@pytest.mark.django_db
def test_reject(submission, state):
    submission.state = state
    submission.save()
    count = submission.logged_actions().count()

    submission.reject()

    assert submission.state == SubmissionStates.REJECTED
    assert submission.logged_actions().count() == (count + 1)
    assert submission.event.queued_mails.count() == 1
    assert submission.event.wip_schedule.talks.count() == 0
