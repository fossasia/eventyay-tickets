import pytest

from pretalx.submission.models import SubmissionError, SubmissionStates


@pytest.mark.parametrize('state', (
    SubmissionStates.SUBMITTED,
    SubmissionStates.REJECTED,
    SubmissionStates.CONFIRMED,
    SubmissionStates.CANCELED,
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
    SubmissionStates.ACCEPTED,
))
@pytest.mark.django_db
def test_reject_success(submission, state):
    submission.state = state
    submission.save()
    count = submission.logged_actions().count()

    submission.reject()

    assert submission.state == SubmissionStates.REJECTED
    assert submission.logged_actions().count() == (count + 1)
    assert submission.event.queued_mails.count() == 1
    assert submission.event.wip_schedule.talks.count() == 0


@pytest.mark.parametrize('state', (
    SubmissionStates.REJECTED,
    SubmissionStates.CONFIRMED,
    SubmissionStates.CANCELED,
    SubmissionStates.WITHDRAWN,
))
@pytest.mark.parametrize('force', (True, False))
@pytest.mark.django_db
def test_reject_fail(submission, state, force):
    submission.state = state
    submission.save()
    count = submission.logged_actions().count()

    if force:
        submission.reject(force=force)

        assert submission.state == SubmissionStates.REJECTED
        assert submission.logged_actions().count() == (count + 1)
        assert submission.event.queued_mails.count() == 1
        assert submission.event.wip_schedule.talks.count() == 0
    else:
        with pytest.raises(SubmissionError):
            submission.reject(force=force)
        assert submission.state == state
        assert submission.logged_actions().count() == count
        assert submission.event.queued_mails.count() == 0
        assert submission.event.wip_schedule.talks.count() == 0


@pytest.mark.parametrize('state', (
    SubmissionStates.ACCEPTED,
    SubmissionStates.CONFIRMED,
))
@pytest.mark.django_db
def test_cancel_success(submission, state):
    submission.state = state
    submission.save()
    count = submission.logged_actions().count()

    submission.cancel()

    assert submission.state == SubmissionStates.CANCELED
    assert submission.logged_actions().count() == (count + 1)
    assert submission.event.queued_mails.count() == 0
    assert submission.event.wip_schedule.talks.count() == 0


@pytest.mark.parametrize('state', (
    SubmissionStates.SUBMITTED,
    SubmissionStates.REJECTED,
    SubmissionStates.CANCELED,
    SubmissionStates.WITHDRAWN,
))
@pytest.mark.django_db
def test_cancel_fail(submission, state):
    submission.state = state
    submission.save()

    with pytest.raises(SubmissionError):
        submission.cancel()
    assert submission.state == state
    assert submission.event.queued_mails.count() == 0
    assert submission.event.wip_schedule.talks.count() == 0
    assert submission.logged_actions().count() == 0


@pytest.mark.parametrize('state', (
    SubmissionStates.SUBMITTED,
))
@pytest.mark.django_db
def test_withdraw_success(submission, state):
    submission.state = state
    submission.save()
    count = submission.logged_actions().count()

    submission.withdraw()

    assert submission.state == SubmissionStates.WITHDRAWN
    assert submission.logged_actions().count() == (count + 1)
    assert submission.event.queued_mails.count() == 0
    assert submission.event.wip_schedule.talks.count() == 0


@pytest.mark.parametrize('state', (
    SubmissionStates.ACCEPTED,
    SubmissionStates.CONFIRMED,
    SubmissionStates.REJECTED,
    SubmissionStates.CANCELED,
    SubmissionStates.WITHDRAWN,
))
@pytest.mark.django_db
def test_withdraw_fail(submission, state):
    submission.state = state
    submission.save()

    with pytest.raises(SubmissionError):
        submission.withdraw()
    assert submission.state == state
    assert submission.event.queued_mails.count() == 0
    assert submission.event.wip_schedule.talks.count() == 0
    assert submission.logged_actions().count() == 0


@pytest.mark.django_db
def test_set_state_error_msg(submission):
    submission.state = SubmissionStates.SUBMITTED

    with pytest.raises(SubmissionError) as excinfo:
        submission._set_state(SubmissionStates.SUBMITTED)

    assert 'must be rejected or accepted or withdrawn not submitted to be submitted' in str(excinfo.value)


@pytest.mark.parametrize('state,expected', (
    (SubmissionStates.ACCEPTED, False),
    (SubmissionStates.DELETED, True)
))
@pytest.mark.django_db
def test_is_deleted(submission, state, expected):
    submission.state = state
    submission.save()

    assert submission.is_deleted == expected
