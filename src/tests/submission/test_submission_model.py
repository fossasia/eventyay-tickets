import pytest

from pretalx.submission.models import Answer, SubmissionError, SubmissionStates
from pretalx.submission.models.submission import submission_image_path


@pytest.mark.parametrize(
    'state',
    (
        SubmissionStates.SUBMITTED,
        SubmissionStates.ACCEPTED,
        SubmissionStates.REJECTED,
        SubmissionStates.CONFIRMED,
        SubmissionStates.CANCELED,
    ),
)
@pytest.mark.django_db
def test_accept_success(submission, state):
    submission.state = state
    submission.save()
    count = submission.logged_actions().count()

    submission.accept()

    assert submission.state == SubmissionStates.ACCEPTED
    assert submission.logged_actions().count() == (count + 1)
    if state != SubmissionStates.CONFIRMED:
        assert submission.event.queued_mails.count() == 1
    else:
        assert submission.event.queued_mails.count() == 0
    assert submission.event.wip_schedule.talks.count() == 1


@pytest.mark.parametrize('state', (SubmissionStates.WITHDRAWN,))
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


@pytest.mark.parametrize(
    'state', (SubmissionStates.SUBMITTED, SubmissionStates.ACCEPTED)
)
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


@pytest.mark.parametrize(
    'state',
    (SubmissionStates.CONFIRMED, SubmissionStates.CANCELED, SubmissionStates.WITHDRAWN),
)
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


@pytest.mark.parametrize(
    'state', (SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED)
)
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


@pytest.mark.parametrize(
    'state',
    (SubmissionStates.SUBMITTED, SubmissionStates.REJECTED, SubmissionStates.WITHDRAWN),
)
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


@pytest.mark.parametrize('state', (SubmissionStates.SUBMITTED,))
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


@pytest.mark.parametrize(
    'state',
    (
        SubmissionStates.ACCEPTED,
        SubmissionStates.CONFIRMED,
        SubmissionStates.REJECTED,
        SubmissionStates.CANCELED,
    ),
)
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


@pytest.mark.parametrize(
    'state',
    (
        SubmissionStates.ACCEPTED,
        SubmissionStates.CONFIRMED,
        SubmissionStates.REJECTED,
        SubmissionStates.CANCELED,
        SubmissionStates.WITHDRAWN,
    ),
)
@pytest.mark.django_db
def test_make_submitted(submission, state):
    submission.state = state
    submission.save()

    submission.make_submitted(force=True)
    assert submission.state == SubmissionStates.SUBMITTED
    assert submission.event.queued_mails.count() == 0
    assert submission.event.wip_schedule.talks.count() == 0
    assert submission.logged_actions().count() == 0


@pytest.mark.django_db
def test_submission_set_state_error_msg(submission):
    submission.state = SubmissionStates.CANCELED

    with pytest.raises(SubmissionError) as excinfo:
        submission._set_state(SubmissionStates.SUBMITTED)

    assert (
        'must be rejected or accepted or withdrawn not canceled to be submitted'
        in str(excinfo.value)
    )


@pytest.mark.parametrize(
    'state,expected',
    ((SubmissionStates.ACCEPTED, False), (SubmissionStates.DELETED, True)),
)
@pytest.mark.django_db
def test_submission_is_deleted(submission, state, expected):
    submission.state = state
    submission.save()

    assert submission.is_deleted == expected


@pytest.mark.django_db
def test_submission_remove_removes_answers(submission, answer):
    count = Answer.objects.count()
    answer_count = submission.answers.count()
    assert answer_count
    submission.remove(force=True)
    assert submission.is_deleted
    assert Answer.objects.count() == count - answer_count


@pytest.mark.django_db
def test_submission_recording_iframe(submission):
    submission.recording_url = submission.recording_source = 'https://example.org'
    assert (
        submission.rendered_recording_iframe
        == '<div class="embed-responsive embed-responsive-16by9"><iframe src="https://example.org" frameborder="0" allowfullscreen></iframe></div>'
    )


@pytest.mark.django_db
def test_nonstandard_duration(submission):
    assert submission.get_duration() == submission.submission_type.default_duration
    submission.duration = 9
    assert submission.get_duration() == 9


@pytest.mark.django_db
def test_submission_image_path(submission):
    assert submission_image_path(submission, 'foo') == f'{submission.event.slug}/images/{submission.code}/foo'


@pytest.mark.django_db
def test_submission_change_slot_count(accepted_submission):
    assert accepted_submission.slots.filter(schedule=accepted_submission.event.wip_schedule).count() == 1
    accepted_submission.event.settings.present_multiple_times = True
    accepted_submission.slot_count = 2
    accepted_submission.save()
    accepted_submission.accept()
    assert accepted_submission.slots.filter(schedule=accepted_submission.event.wip_schedule).count() == 2
    accepted_submission.slot_count = 1
    accepted_submission.save()
    accepted_submission.accept()
    assert accepted_submission.slots.filter(schedule=accepted_submission.event.wip_schedule).count() == 1
