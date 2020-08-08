import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django_scopes import scope

from pretalx.common.exceptions import SubmissionError
from pretalx.submission.models import Answer, Submission, SubmissionStates
from pretalx.submission.models.submission import submission_image_path


@pytest.mark.parametrize(
    "state",
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
    with scope(event=submission.event):
        submission.state = state
        submission.save()
        count = submission.logged_actions().count()

        submission.accept()
        assert submission.state == SubmissionStates.ACCEPTED
        assert submission.event.queued_mails.count() == int(
            state != SubmissionStates.CONFIRMED
        )
        assert submission.logged_actions().count() == (count + 1)
        assert submission.event.wip_schedule.talks.count() == 1


@pytest.mark.parametrize("state", (SubmissionStates.WITHDRAWN,))
@pytest.mark.parametrize("force", (True, False))
@pytest.mark.django_db
def test_accept_fail(submission, state, force):
    with scope(event=submission.event):
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
    "state", (SubmissionStates.SUBMITTED, SubmissionStates.ACCEPTED)
)
@pytest.mark.django_db
def test_reject_success(submission, state):
    with scope(event=submission.event):
        submission.state = state
        submission.save()
        count = submission.logged_actions().count()

        submission.reject()

        assert submission.state == SubmissionStates.REJECTED
        assert submission.logged_actions().count() == (count + 1)
        assert submission.event.queued_mails.count() == 1
        assert submission.event.wip_schedule.talks.count() == 0


@pytest.mark.parametrize(
    "state",
    (SubmissionStates.CONFIRMED, SubmissionStates.CANCELED, SubmissionStates.WITHDRAWN),
)
@pytest.mark.parametrize("force", (True, False))
@pytest.mark.django_db
def test_reject_fail(submission, state, force):
    with scope(event=submission.event):
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
    "state", (SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED)
)
@pytest.mark.django_db
def test_cancel_success(submission, state):
    with scope(event=submission.event):
        submission.state = state
        submission.save()
        count = submission.logged_actions().count()

        submission.cancel()

        assert submission.state == SubmissionStates.CANCELED
        assert submission.logged_actions().count() == (count + 1)
        assert submission.event.queued_mails.count() == 0
        assert submission.event.wip_schedule.talks.count() == 0


@pytest.mark.parametrize(
    "state",
    (SubmissionStates.SUBMITTED, SubmissionStates.REJECTED, SubmissionStates.WITHDRAWN),
)
@pytest.mark.django_db
def test_cancel_fail(submission, state):
    with scope(event=submission.event):
        submission.state = state
        submission.save()

        with pytest.raises(SubmissionError):
            submission.cancel()
        assert submission.state == state
        assert submission.event.queued_mails.count() == 0
        assert submission.event.wip_schedule.talks.count() == 0
        assert submission.logged_actions().count() == 0


@pytest.mark.parametrize(
    "state", (SubmissionStates.SUBMITTED, SubmissionStates.ACCEPTED)
)
@pytest.mark.django_db
def test_withdraw_success(submission, state):
    with scope(event=submission.event):
        submission.state = state
        submission.save()
        count = submission.logged_actions().count()

        submission.withdraw()

        assert submission.state == SubmissionStates.WITHDRAWN
        assert submission.logged_actions().count() == (count + 1)
        assert submission.event.queued_mails.count() == 0
        assert submission.event.wip_schedule.talks.count() == 0


@pytest.mark.parametrize(
    "state",
    (SubmissionStates.CONFIRMED, SubmissionStates.REJECTED, SubmissionStates.CANCELED,),
)
@pytest.mark.django_db
def test_withdraw_fail(submission, state):
    with scope(event=submission.event):
        submission.state = state
        submission.save()

        with pytest.raises(SubmissionError):
            submission.withdraw()
        assert submission.state == state
        assert submission.event.queued_mails.count() == 0
        assert submission.event.wip_schedule.talks.count() == 0
        assert submission.logged_actions().count() == 0


@pytest.mark.parametrize(
    "state",
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
    with scope(event=submission.event):
        submission.state = state
        submission.save()

        submission.make_submitted(force=True)
        assert submission.state == SubmissionStates.SUBMITTED
        assert submission.event.queued_mails.count() == 0
        assert submission.event.wip_schedule.talks.count() == 0
        assert submission.logged_actions().count() == 0


@pytest.mark.django_db
def test_submission_set_state_error_msg(submission):
    with scope(event=submission.event):
        submission.state = SubmissionStates.CANCELED

        with pytest.raises(SubmissionError) as excinfo:
            submission._set_state(SubmissionStates.SUBMITTED)

        assert (
            "must be rejected or accepted or withdrawn not canceled to be submitted"
            in str(excinfo.value)
        )


@pytest.mark.parametrize(
    "state,expected",
    ((SubmissionStates.ACCEPTED, False), (SubmissionStates.DELETED, True)),
)
@pytest.mark.django_db
def test_submission_is_deleted(submission, state, expected):
    with scope(event=submission.event):
        submission.state = state
        submission.save()

        assert submission.is_deleted == expected


@pytest.mark.django_db
def test_submission_remove_removes_answers(submission, answer):
    with scope(event=submission.event):
        count = Answer.objects.count()
        answer_count = submission.answers.count()
        assert answer_count
        submission.remove(force=True)
        assert submission.is_deleted
        assert Answer.objects.count() == count - answer_count


@pytest.mark.django_db
def test_nonstandard_duration(submission):
    assert submission.get_duration() == submission.submission_type.default_duration
    submission.duration = 9
    assert submission.get_duration() == 9


@pytest.mark.django_db
def test_submission_image_path(submission):
    assert submission_image_path(submission, "foo").startswith(
        f"{submission.event.slug}/submissions/{submission.code}"
    )


@pytest.mark.django_db
def test_submission_change_slot_count(accepted_submission):
    with scope(event=accepted_submission.event):
        assert (
            accepted_submission.slots.filter(
                schedule=accepted_submission.event.wip_schedule
            ).count()
            == 1
        )
        accepted_submission.event.settings.present_multiple_times = True
        accepted_submission.slot_count = 2
        accepted_submission.save()
        accepted_submission.accept()
        assert (
            accepted_submission.slots.filter(
                schedule=accepted_submission.event.wip_schedule
            ).count()
            == 2
        )
        accepted_submission.slot_count = 1
        accepted_submission.save()
        accepted_submission.accept()
        assert (
            accepted_submission.slots.filter(
                schedule=accepted_submission.event.wip_schedule
            ).count()
            == 1
        )


@pytest.mark.django_db
def test_submission_assign_code(submission, monkeypatch):
    from pretalx.common.mixins import models as models_mixins
    from pretalx.submission.models import submission as pretalx_submission

    called = -1
    submission_codes = [submission.code, submission.code, "abcdef"]

    def yield_random_codes(*args, **kwargs):
        nonlocal called
        called += 1
        return submission_codes[called]

    monkeypatch.setattr(models_mixins, "get_random_string", yield_random_codes)
    new_submission = pretalx_submission.Submission()
    assert not new_submission.code
    new_submission.assign_code()
    assert new_submission.code == "abcdef"
    assert new_submission.code != submission.code


@pytest.mark.parametrize(
    "data,loaded",
    (
        ("", {}),
        (None, {}),
        ("{}", {}),
        ("[]", {}),
        ("[1,2,3]", {}),
        ('{"a": "b"}', {"a": "b"}),
        ("1saser;", {}),
    ),
)
def test_submission_anonymise(data, loaded):
    s = Submission()
    s.anonymised_data = data
    assert s.anonymised == loaded
    assert not s.is_anonymised


@pytest.mark.parametrize(
    "state,expected",
    (
        (SubmissionStates.SUBMITTED, 0),
        (SubmissionStates.ACCEPTED, 1),
        (SubmissionStates.REJECTED, 1),
        (SubmissionStates.CONFIRMED, 0),
        (SubmissionStates.CANCELED, 0),
    ),
)
@pytest.mark.django_db
def test_send_state_mail(submission, state, expected):
    with scope(event=submission.event):
        submission.state = state
        submission.save()
        count = submission.event.queued_mails.all().count()
        submission.send_state_mail()
        assert submission.event.queued_mails.all().count() == count + expected


@pytest.mark.django_db
def test_public_slots_without_schedule(submission):
    with scope(event=submission.event):
        submission.event.schedules.all().delete()
        submission.event.is_public = True
        submission.event.settings.show_schedule = True
        submission.event.save()
        assert submission.public_slots == []


@pytest.mark.django_db
def test_public_slots_with_visible_agenda(submission, slot):
    with scope(event=submission.event):
        submission.event.is_public = True
        submission.event.settings.show_schedule = True
        submission.event.save()
        assert len(submission.public_slots) == 0


@pytest.mark.django_db
def test_content_for_mail(submission, file_question, boolean_question):
    f = SimpleUploadedFile("testresource.txt", b"a resource")
    with scope(event=submission.event):
        Answer.objects.create(
            question=boolean_question, answer=True, submission=submission
        )
        fa = Answer.objects.create(
            question=file_question, answer_file=f, submission=submission
        )
        host = submission.event.settings.custom_domain or settings.SITE_URL

        assert (
            submission.get_content_for_mail().strip()
            == f"""**Title**: {submission.title}

**Abstract**: {submission.abstract}

**Description**: {submission.description}

**Notes**: {submission.notes}

**Language**: {submission.content_locale}

**{boolean_question.question}**: Yes

**{file_question.question}**: {host}{fa.answer_file.url}""".strip()
        )


@pytest.mark.django_db
def test_send_invite_requires_signature(submission):
    with scope(event=submission.event):
        with pytest.raises(Exception):
            submission.send_invite(None)
