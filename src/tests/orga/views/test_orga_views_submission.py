import datetime as dt

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now
from django_scopes import scope

from pretalx.common.models.log import ActivityLog
from pretalx.submission.models import Submission, SubmissionStates
from pretalx.submission.models.question import QuestionRequired, QuestionVariant


@pytest.mark.django_db
def test_orga_can_see_submissions(orga_client, event, submission):
    response = orga_client.get(event.orga_urls.submissions, follow=True)
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_orga_can_search_submissions(orga_client, event, submission):
    response = orga_client.get(
        event.orga_urls.submissions + f"?q={submission.title[:5]}", follow=True
    )
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_orga_can_search_submissions_by_speaker(orga_client, event, submission):
    response = orga_client.get(
        event.orga_urls.submissions + f"?q={submission.speakers.first().name[:5]}",
        follow=True,
    )
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_reviewer_can_search_submissions_by_speaker(review_client, event, submission):
    response = review_client.get(
        event.orga_urls.submissions
        + f"?q={submission.speakers.first().name[:5]}&state=submitted",
        follow=True,
    )
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_reviewer_cannot_search_submissions_by_speaker_when_anonymised(
    review_client, event, submission, review_user
):
    with scope(event=event):
        submission.event.active_review_phase.can_see_speaker_names = False
        submission.event.active_review_phase.save()
        assert not review_user.has_perm("orga.view_speakers", event)
    response = review_client.get(
        event.orga_urls.submissions + f"?q={submission.speakers.first().name[:5]}",
        follow=True,
    )
    assert response.status_code == 200
    assert submission.title not in response.content.decode()


@pytest.mark.django_db
def test_reviewer_cannot_search_submissions_by_speaker_when_anonymised_on_team_level(
    review_client, event, submission, review_user
):
    with scope(event=event):
        team = review_user.teams.all().filter(is_reviewer=True).first()
        team.force_hide_speaker_names = True
        team.save()
        assert submission.event.active_review_phase.can_see_speaker_names
        assert not review_user.has_perm("orga.view_speakers", event)
    response = review_client.get(
        event.orga_urls.submissions + f"?q={submission.speakers.first().name[:5]}",
        follow=True,
    )
    assert response.status_code == 200
    assert submission.title not in response.content.decode()


@pytest.mark.django_db
def test_orga_can_miss_search_submissions(orga_client, event, submission):
    response = orga_client.get(
        event.orga_urls.submissions + f"?q={submission.title[:5]}xxy", follow=True
    )
    assert response.status_code == 200
    assert submission.title not in response.content.decode()


@pytest.mark.django_db
def test_orga_can_see_single_submission(orga_client, event, submission):
    response = orga_client.get(submission.orga_urls.base, follow=True)
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_orga_can_see_submission_404(orga_client, event, submission):
    response = orga_client.get(submission.orga_urls.base + "JJ", follow=True)
    assert response.status_code == 404
    assert submission.title not in response.content.decode()


@pytest.mark.django_db
def test_reviewer_can_see_single_submission(review_client, event, submission, answer):
    event.feature_flags["use_tracks"] = True
    event.save()
    response = review_client.get(submission.orga_urls.base, follow=True)
    assert response.status_code == 200
    assert submission.title in response.content.decode()
    with scope(event=event):
        assert answer.question.question in response.content.decode()


@pytest.mark.django_db
def test_reviewer_can_see_single_submission_but_hide_question(
    review_client, event, submission, answer
):
    with scope(event=event):
        answer.question.is_visible_to_reviewers = False
        answer.question.save()
    event.feature_flags["use_tracks"] = True
    event.save()
    response = review_client.get(submission.orga_urls.base, follow=True)
    assert response.status_code == 200
    assert submission.title in response.content.decode()
    with scope(event=event):
        assert answer.question.question not in response.content.decode()


@pytest.mark.django_db
def test_orga_can_see_single_submission_feedback(orga_client, event, feedback):
    response = orga_client.get(feedback.talk.orga_urls.feedback, follow=True)
    assert response.status_code == 200
    assert feedback.review in response.content.decode()


@pytest.mark.django_db
def test_orga_can_see_single_submission_speakers(orga_client, event, submission):
    response = orga_client.get(submission.orga_urls.speakers, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_can_see_single_submission_in_feed(orga_client, event, submission):
    response = orga_client.get(submission.event.orga_urls.submission_feed, follow=True)
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_wrong_user_cannot_see_single_submission_in_feed(
    client, user, event, submission
):
    user.teams.remove(user.teams.first())
    response = client.get(submission.event.orga_urls.submission_feed, follow=True)
    assert submission.title not in response.content.decode()


@pytest.mark.django_db
def test_accept_submission(orga_client, submission):
    assert submission.state == SubmissionStates.SUBMITTED

    response = orga_client.get(submission.orga_urls.accept, follow=True)
    submission.refresh_from_db()
    assert response.status_code == 200
    assert submission.state == SubmissionStates.SUBMITTED
    response = orga_client.post(submission.orga_urls.accept, follow=True)
    assert response.status_code == 200

    with scope(event=submission.event):
        submission.refresh_from_db()
        assert submission.event.queued_mails.count() == 1
        assert submission.state == SubmissionStates.ACCEPTED


@pytest.mark.django_db
def test_accept_submission_redirects_to_review_list(orga_client, submission):
    assert submission.state == SubmissionStates.SUBMITTED

    response = orga_client.post(
        submission.orga_urls.accept + f"?next={submission.event.orga_urls.reviews}"
    )
    redirected_page_url = response.headers["location"]

    assert response.status_code == 302
    assert redirected_page_url == submission.event.orga_urls.reviews


@pytest.mark.django_db
def test_accept_accepted_submission(orga_client, submission):
    with scope(event=submission.event):
        submission.accept()
    response = orga_client.post(submission.orga_urls.accept, follow=True)
    assert response.status_code == 200
    with scope(event=submission.event):
        submission.refresh_from_db()
    assert submission.state == "accepted"


@pytest.mark.django_db
def test_reject_submission(orga_client, submission):
    with scope(event=submission.event):
        assert submission.event.queued_mails.count() == 0
    assert submission.state == SubmissionStates.SUBMITTED

    response = orga_client.get(submission.orga_urls.reject, follow=True)
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert submission.state == SubmissionStates.SUBMITTED
    assert response.status_code == 200
    response = orga_client.post(submission.orga_urls.reject, follow=True)
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert submission.event.queued_mails.count() == 1

    assert response.status_code == 200
    assert submission.state == SubmissionStates.REJECTED


@pytest.mark.django_db
def test_orga_can_confirm_submission(orga_client, accepted_submission):
    assert accepted_submission.state == SubmissionStates.ACCEPTED

    response = orga_client.get(accepted_submission.orga_urls.confirm, follow=True)
    accepted_submission.refresh_from_db()
    assert accepted_submission.state == SubmissionStates.ACCEPTED
    assert response.status_code == 200
    response = orga_client.post(accepted_submission.orga_urls.confirm, follow=True)
    accepted_submission.refresh_from_db()

    assert response.status_code == 200
    assert accepted_submission.state == SubmissionStates.CONFIRMED


@pytest.mark.django_db
def test_orga_can_delete_submission(orga_client, submission, answered_choice_question):
    with scope(event=submission.event):
        assert submission.state == SubmissionStates.SUBMITTED
        assert submission.answers.count() == 1
        assert Submission.objects.count() == 1
        option_count = answered_choice_question.options.count()

    response = orga_client.get(submission.orga_urls.delete, follow=True)
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert response.status_code == 200
        assert submission.state == SubmissionStates.SUBMITTED
        assert Submission.objects.count() == 1

    response = orga_client.post(submission.orga_urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=submission.event):
        assert Submission.objects.count() == 0
        assert Submission.deleted_objects.count() == 1
        assert Submission.deleted_objects.get(code=submission.code)
        assert answered_choice_question.options.count() == option_count


@pytest.mark.django_db
def test_reviewer_cannot_delete_submission(
    review_client, submission, answered_choice_question
):
    with scope(event=submission.event):
        assert submission.state == SubmissionStates.SUBMITTED
        assert submission.answers.count() == 1
        assert Submission.objects.count() == 1

    response = review_client.get(submission.orga_urls.delete, follow=True)
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert response.status_code == 404
        assert submission.state == SubmissionStates.SUBMITTED
        assert Submission.objects.count() == 1

    response = review_client.post(submission.orga_urls.delete, follow=True)
    assert response.status_code == 404
    with scope(event=submission.event):
        assert Submission.objects.count() == 1
        assert Submission.deleted_objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("user", ("EMAIL", "NEW_EMAIL"))
def test_orga_can_add_speakers(orga_client, submission, other_orga_user, user):
    assert submission.speakers.count() == 1

    if user == "EMAIL":
        user = other_orga_user.email
    else:
        user = "some_unused@mail.org"

    response = orga_client.post(
        submission.orga_urls.new_speaker,
        data={"speaker": user, "name": "Name"},
        follow=True,
    )
    submission.refresh_from_db()

    assert submission.speakers.count() == 2
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_can_add_speakers_with_incorrect_address(orga_client, submission):
    assert submission.speakers.count() == 1
    response = orga_client.post(
        submission.orga_urls.new_speaker,
        data={"speaker": "foooobaaaaar", "name": "Name"},
        follow=True,
    )
    submission.refresh_from_db()
    assert response.status_code == 200
    assert submission.speakers.count() == 1


@pytest.mark.django_db
def test_orga_can_readd_speaker(orga_client, submission):
    assert submission.speakers.count() == 1
    response = orga_client.post(
        submission.orga_urls.new_speaker,
        data={"speaker": submission.speakers.first().email, "name": "Name"},
        follow=True,
    )
    submission.refresh_from_db()
    assert response.status_code == 200
    assert submission.speakers.count() == 1


@pytest.mark.django_db
def test_orga_can_remove_speaker(orga_client, submission):
    assert submission.speakers.count() == 1
    response = orga_client.get(
        submission.orga_urls.delete_speaker
        + "?id="
        + str(submission.speakers.first().pk),
        follow=True,
    )
    submission.refresh_from_db()
    assert response.status_code == 200
    assert submission.speakers.count() == 0


@pytest.mark.django_db
def test_orga_can_remove_wrong_speaker(orga_client, submission, other_speaker):
    assert submission.speakers.count() == 1
    response = orga_client.get(
        submission.orga_urls.delete_speaker + "?id=" + str(other_speaker.pk),
        follow=True,
    )
    submission.refresh_from_db()
    assert response.status_code == 200
    assert submission.speakers.count() == 1
    assert "not part of this proposal" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("known_speaker", (True, False))
def test_orga_can_create_submission(orga_client, event, known_speaker, orga_user):
    with scope(event=event):
        assert event.submissions.count() == 0
        type_pk = event.submission_types.first().pk

    response = orga_client.post(
        event.orga_urls.new_submission,
        data={
            "abstract": "abstract",
            "content_locale": "en",
            "description": "description",
            "duration": "",
            "slot_count": 1,
            "notes": "notes",
            "internal_notes": "internal_notes",
            "speaker": "foo@bar.com" if not known_speaker else orga_user.email,
            "speaker_name": "Foo Speaker",
            "title": "title",
            "submission_type": type_pk,
            "state": "submitted",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.submissions.count() == 1
        sub = event.submissions.first()
        assert sub.title == "title"
        assert sub.speakers.count() == 1


@pytest.mark.django_db
def test_orga_can_edit_submission(orga_client, event, accepted_submission):
    event.feature_flags["present_multiple_times"] = True
    event.save()
    with scope(event=event):
        assert event.submissions.count() == 1
        assert accepted_submission.slots.count() == 1

    response = orga_client.post(
        accepted_submission.orga_urls.base,
        data={
            "abstract": "abstract",
            "content_locale": "en",
            "description": "description",
            "duration": "",
            "slot_count": 2,
            "notes": "notes",
            "speaker": "foo@bar.com",
            "speaker_name": "Foo Speaker",
            "title": "title",
            "submission_type": accepted_submission.submission_type.pk,
            "resource-TOTAL_FORMS": 0,
            "resource-INITIAL_FORMS": 0,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        accepted_submission.refresh_from_db()
        assert event.submissions.count() == 1
        assert accepted_submission.slot_count == 2
        assert accepted_submission.slots.count() == 2


@pytest.mark.django_db
def test_orga_can_remove_and_add_resources(
    orga_client, event, submission, resource, other_resource
):
    with scope(event=submission.event):
        assert submission.resources.count() == 2
        resource_one = submission.resources.first()
        resource_two = submission.resources.last()

    f = SimpleUploadedFile("testfile.txt", b"file_content")
    response = orga_client.post(
        submission.orga_urls.base,
        data={
            "abstract": submission.abstract,
            "content_locale": submission.content_locale,
            "title": "new title",
            "submission_type": submission.submission_type.pk,
            "resource-0-id": resource_one.id,
            "resource-0-description": "new resource name",
            "resource-0-resource": resource_one.resource,
            "resource-1-id": resource_two.id,
            "resource-1-DELETE": True,
            "resource-1-description": resource_two.description,
            "resource-1-resource": resource_two.resource,
            "resource-2-id": "",
            "resource-2-description": "new resource",
            "resource-2-resource": f,
            "resource-TOTAL_FORMS": 3,
            "resource-INITIAL_FORMS": 2,
            "resource-MIN_NUM_FORMS": 0,
            "resource-MAX_NUM_FORMS": 1000,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        submission.refresh_from_db()
        resource_one.refresh_from_db()
        new_resource = submission.resources.exclude(pk=resource_one.pk).first()
        assert submission.title == "new title"
        assert submission.resources.count() == 2
        assert new_resource.description == "new resource"
        assert new_resource.resource.read() == b"file_content"
        assert not submission.resources.filter(pk=resource_two.pk).exists()


@pytest.mark.django_db
def test_orga_edit_submission_with_wrong_resources(
    orga_client, event, submission, resource, other_resource
):
    with scope(event=submission.event):
        assert submission.resources.count() == 2
        resource_one = submission.resources.first()
        resource_two = submission.resources.last()

    f = SimpleUploadedFile("testfile.txt", b"file_content")
    response = orga_client.post(
        submission.orga_urls.base,
        data={
            "abstract": submission.abstract,
            "content_locale": submission.content_locale,
            "title": "new title",
            "submission_type": submission.submission_type.pk,
            "resource-0-id": resource_one.id,
            "resource-0-description": "new resource name",
            "resource-0-resource": resource_one.resource,
            "resource-1-id": resource_two.id,
            "resource-1-DELETE": True,
            "resource-1-description": resource_two.description,
            "resource-1-resource": resource_two.resource,
            "resource-2-id": "",
            "resource-2-description": "",
            "resource-2-resource": f,
            "resource-TOTAL_FORMS": 3,
            "resource-INITIAL_FORMS": 2,
            "resource-MIN_NUM_FORMS": 0,
            "resource-MAX_NUM_FORMS": 1000,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        submission.refresh_from_db()
        resource_one.refresh_from_db()
        new_resource = submission.resources.exclude(pk=resource_one.pk).first()
        assert submission.resources.count() == 2
        assert new_resource == other_resource


@pytest.mark.django_db
def test_orga_can_edit_submission_wrong_answer(
    orga_client, event, accepted_submission, question
):
    event.feature_flags["present_multiple_times"] = True
    event.save()
    with scope(event=event):
        question.question_required = QuestionRequired.REQUIRED
        question.save()
        assert event.submissions.count() == 1
        assert accepted_submission.slots.count() == 1

    response = orga_client.post(
        accepted_submission.orga_urls.base,
        data={
            "abstract": "abstract",
            "content_locale": "en",
            "description": "description",
            "duration": "",
            "slot_count": 2,
            "notes": "notes",
            "speaker": "foo@bar.com",
            "speaker_name": "Foo Speaker",
            "title": "new title",
            "submission_type": accepted_submission.submission_type.pk,
            "resource-TOTAL_FORMS": 0,
            "resource-INITIAL_FORMS": 0,
            f"question_{question.pk}": "hahaha",
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        accepted_submission.refresh_from_db()
        assert accepted_submission.title != "new title"


@pytest.mark.django_db
def test_orga_can_edit_submission_duration(orga_client, event, accepted_submission):
    with scope(event=event):
        slot = accepted_submission.slots.filter(schedule=event.wip_schedule).first()
        slot.start = now()
        slot.end = slot.start + dt.timedelta(minutes=accepted_submission.get_duration())
        slot.save()
        assert slot.duration == accepted_submission.get_duration()

    response = orga_client.post(
        accepted_submission.orga_urls.base,
        data={
            "abstract": "abstract",
            "content_locale": "en",
            "description": "description",
            "slot_count": 2,
            "notes": "notes",
            "speaker": "foo@bar.com",
            "speaker_name": "Foo Speaker",
            "duration": 123,
            "title": "title",
            "submission_type": accepted_submission.submission_type.pk,
            "resource-TOTAL_FORMS": 0,
            "resource-INITIAL_FORMS": 0,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        slot.refresh_from_db()
        assert (slot.end - slot.start).seconds / 60 == 123


@pytest.mark.django_db
def test_orga_can_toggle_submission_featured(orga_client, event, submission):
    with scope(event=event):
        assert event.submissions.count() == 1

    response = orga_client.post(submission.orga_urls.toggle_featured, follow=True)

    assert response.status_code == 200
    with scope(event=event):
        sub = event.submissions.first()
        assert sub.is_featured


@pytest.mark.parametrize(
    "question_type", (QuestionVariant.DATE, QuestionVariant.DATETIME)
)
@pytest.mark.parametrize(
    "delta,success",
    (
        (dt.timedelta(days=-1), False),
        (dt.timedelta(days=1), True),
        (dt.timedelta(days=3), False),
    ),
)
@pytest.mark.django_db
def test_orga_can_edit_submission_wrong_datetime_answer(
    orga_client, event, submission, question, question_type, delta, success
):
    min_value = now()
    max_value = now() + dt.timedelta(days=2)
    with scope(event=event):
        question.question_required = QuestionRequired.REQUIRED
        question.variant = question_type
        question.min_date = min_value.date()
        question.min_datetime = min_value
        question.max_date = max_value.date()
        question.max_datetime = max_value
        question.save()

    value = min_value + delta
    if question_type == QuestionVariant.DATE:
        value = value.date()
    value = value.isoformat()
    response = orga_client.post(
        submission.orga_urls.base,
        data={
            "abstract": "abstract",
            "content_locale": "en",
            "description": "description",
            "duration": "",
            "slot_count": 2,
            "notes": "notes",
            "title": "new title",
            "submission_type": submission.submission_type_id,
            "resource-TOTAL_FORMS": 0,
            "resource-INITIAL_FORMS": 0,
            f"question_{question.pk}": value,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        submission.refresh_from_db()
        assert (submission.title == "new title") is success


@pytest.mark.django_db
def test_orga_can_see_all_feedback(orga_client, event, feedback):
    response = orga_client.get(event.orga_urls.feedback, follow=True)
    assert response.status_code == 200
    assert feedback.talk.title in response.content.decode()
    assert feedback.review in response.content.decode()


@pytest.mark.django_db
def test_orga_can_see_anonymisation_interface(orga_client, submission):
    response = orga_client.get(submission.orga_urls.anonymise, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_can_anonymise_submission(
    orga_client, review_user, submission, other_submission
):
    with scope(event=submission.event):
        submission.event.active_review_phase.can_see_speaker_names = False
        submission.event.active_review_phase.save()
        assert not review_user.has_perm("orga.view_speakers", submission)
    response = orga_client.post(
        submission.orga_urls.anonymise, follow=True, data={"description": "CENSORED!"}
    )
    assert response.status_code == 200
    submission.refresh_from_db()
    assert submission.is_anonymised
    assert submission.anonymised == {
        "_anonymised": True,
        "abstract": "",
        "notes": "",
        "description": "CENSORED!",
        "title": "",
    }
    assert "CENSORED" in submission.anonymised_data
    response = orga_client.post(
        submission.orga_urls.anonymise,
        data={"title": submission.title, "description": "CENSORED!", "action": "next"},
    )
    redirected_page_url = response.headers["location"]
    assert response.status_code == 302
    assert redirected_page_url == other_submission.orga_urls.anonymise
    assert not other_submission.is_anonymised

    submission.refresh_from_db()
    assert submission.is_anonymised
    assert submission.anonymised == {
        "_anonymised": True,
        "abstract": "",
        "notes": "",
        "description": "CENSORED!",
    }

    response = orga_client.get(submission.orga_urls.reviews)
    assert response.status_code == 200
    assert "CENSORED" in response.content.decode()
    response = orga_client.get(submission.orga_urls.base)
    assert response.status_code == 200
    assert "CENSORED" not in response.content.decode()

    orga_client.force_login(review_user)
    response = orga_client.get(submission.orga_urls.reviews)
    assert response.status_code == 200
    assert "CENSORED" in response.content.decode()
    response = orga_client.get(submission.orga_urls.base)
    assert response.status_code == 200
    assert "CENSORED" in response.content.decode()


@pytest.mark.django_db
def test_reviewer_cannot_see_anonymisation_interface(review_client, submission):
    response = review_client.get(submission.orga_urls.anonymise, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("use_tracks", (True, False))
def test_submission_statistics(use_tracks, slot, other_slot, orga_client):
    with scope(event=slot.event):
        slot.event.feature_flags["use_tracks"] = use_tracks
        slot.event.save()
        logs = []
        subs = [slot.submission, other_slot.submission]
        for i in range(2):
            logs.append(subs[i].log_action("pretalx.submission.create"))
        ActivityLog.objects.filter(pk=logs[0].pk).update(
            timestamp=logs[0].timestamp - dt.timedelta(days=2)
        )
    response = orga_client.get(slot.event.orga_urls.stats)
    assert response.status_code == 200


@pytest.mark.django_db
def test_submission_apply_pending(submission, orga_client):
    with scope(event=submission.event):
        submission.state = "submitted"
        submission.pending_state = "accepted"
        submission.save()
        assert submission.event.queued_mails.count() == 0

    response = orga_client.get(submission.event.orga_urls.apply_pending)
    assert response.status_code == 200
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert submission.state == "submitted"
        assert submission.pending_state == "accepted"
        assert submission.event.queued_mails.count() == 0

    response = orga_client.post(submission.event.orga_urls.apply_pending)
    assert response.status_code == 302
    with scope(event=submission.event):
        submission.refresh_from_db()
        assert submission.state == "accepted"
        assert submission.pending_state is None
        assert submission.event.queued_mails.count() == 1

    response = orga_client.get(submission.event.orga_urls.apply_pending)
    assert response.status_code == 200


@pytest.mark.django_db
def test_can_see_tags(orga_client, tag):
    response = orga_client.get(tag.event.orga_urls.tags)
    assert response.status_code == 200
    assert tag.tag in response.content.decode()


@pytest.mark.django_db
def test_can_create_tag_no_duplicates(orga_client, tag):
    with scope(event=tag.event):
        count = tag.event.tags.count()
    response = orga_client.get(tag.event.orga_urls.new_tag)
    assert response.status_code == 200
    response = orga_client.post(
        tag.event.orga_urls.new_tag,
        {"tag": "New tag!", "color": "#ffff99"},
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=tag.event):
        assert tag.event.tags.count() == count + 1
    response = orga_client.post(
        tag.event.orga_urls.new_tag,
        {"tag": "New tag!", "color": "#ffff99"},
        follow=True,
    )
    assert response.status_code == 200
    assert "You already have a tag by this name!" in response.content.decode()
    with scope(event=tag.event):
        assert tag.event.tags.count() == count + 1


@pytest.mark.django_db
def test_can_see_single_tag(orga_client, tag):
    response = orga_client.get(tag.urls.base)
    assert response.status_code == 200
    assert tag.tag in response.content.decode()


@pytest.mark.django_db
def test_can_edit_tag(orga_client, tag):
    with scope(event=tag.event):
        count = tag.logged_actions().count()
    response = orga_client.post(
        tag.urls.base, {"tag": "Name", "color": "#ffff99"}, follow=True
    )
    assert response.status_code == 200
    with scope(event=tag.event):
        assert tag.logged_actions().count() == count + 1
        tag.refresh_from_db()
    assert str(tag.tag) == "Name"


@pytest.mark.django_db
def test_can_edit_tag_without_changes(orga_client, tag):
    with scope(event=tag.event):
        count = tag.logged_actions().count()
    response = orga_client.post(
        tag.urls.base, {"tag": str(tag.tag), "color": tag.color}, follow=True
    )
    assert response.status_code == 200
    with scope(event=tag.event):
        assert tag.logged_actions().count() == count


@pytest.mark.django_db
def test_cannot_set_incorrect_tag_color(orga_client, tag):
    response = orga_client.post(
        tag.urls.base, {"tag": "Name", "color": "#fgff99"}, follow=True
    )
    assert response.status_code == 200
    tag.refresh_from_db()
    assert str(tag.tag) != "Name"


@pytest.mark.django_db
def test_can_delete_single_tag(orga_client, tag, event):
    response = orga_client.get(tag.urls.delete)
    assert response.status_code == 200
    with scope(event=event):
        assert event.tags.count() == 1
    response = orga_client.post(tag.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.tags.count() == 0


@pytest.mark.django_db
def test_can_delete_used_tag(orga_client, tag, event, submission):
    with scope(event=event):
        assert event.tags.count() == 1
        submission.tags.add(tag)
        submission.save()
    response = orga_client.post(tag.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert event.tags.count() == 0
        submission.refresh_from_db()
        assert submission.tags.count() == 0
