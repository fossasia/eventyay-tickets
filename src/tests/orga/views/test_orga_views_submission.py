from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scope

from pretalx.submission.models import Submission, SubmissionStates


@pytest.mark.django_db
def test_orga_can_see_submissions(orga_client, event, submission):
    response = orga_client.get(event.orga_urls.submissions, follow=True)
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_orga_can_search_submissions(orga_client, event, submission):
    response = orga_client.get(
        event.orga_urls.submissions + f'?q={submission.title[:5]}', follow=True
    )
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_orga_can_miss_search_submissions(orga_client, event, submission):
    response = orga_client.get(
        event.orga_urls.submissions + f'?q={submission.title[:5]}xxy', follow=True
    )
    assert response.status_code == 200
    assert submission.title not in response.content.decode()


@pytest.mark.django_db
def test_orga_can_see_single_submission(orga_client, event, submission):
    response = orga_client.get(submission.orga_urls.base, follow=True)
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_reviewer_can_see_single_submission(review_client, event, submission):
    event.settings.use_tracks = True
    response = review_client.get(submission.orga_urls.base, follow=True)
    assert response.status_code == 200
    assert submission.title in response.content.decode()


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
def test_wrong_user_cannot_see_single_submission_in_feed(client, user, event, submission):
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
        submission.orga_urls.accept + f'?next={submission.event.orga_urls.reviews}'
    )
    _, redirected_page_url = response._headers['location']

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
    assert submission.state == 'accepted'


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
@pytest.mark.parametrize('user', ('EMAIL', 'NEW_EMAIL'))
def test_orga_can_add_speakers(orga_client, submission, other_orga_user, user):
    assert submission.speakers.count() == 1

    if user == 'EMAIL':
        user = other_orga_user.email
    elif user == 'NEW_EMAIL':
        user = 'some_unused@mail.org'

    response = orga_client.post(
        submission.orga_urls.new_speaker,
        data={'speaker': user, 'name': 'Name'},
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
        data={'speaker': 'foooobaaaaar', 'name': 'Name'},
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
        data={'speaker': submission.speakers.first().email, 'name': 'Name'},
        follow=True,
    )
    submission.refresh_from_db()
    assert response.status_code == 200
    assert submission.speakers.count() == 1


@pytest.mark.django_db
def test_orga_can_remove_speaker(orga_client, submission):
    assert submission.speakers.count() == 1
    response = orga_client.get(
        submission.orga_urls.delete_speaker + '?id=' + str(submission.speakers.first().pk),
        follow=True,
    )
    submission.refresh_from_db()
    assert response.status_code == 200
    assert submission.speakers.count() == 0


@pytest.mark.django_db
def test_orga_can_remove_wrong_speaker(orga_client, submission):
    assert submission.speakers.count() == 1
    response = orga_client.get(
        submission.orga_urls.delete_speaker + '?id=' + str(submission.speakers.first().pk) + '12',
        follow=True,
    )
    submission.refresh_from_db()
    assert response.status_code == 404
    assert submission.speakers.count() == 1


@pytest.mark.django_db
def test_orga_can_create_submission(orga_client, event):
    with scope(event=event):
        assert event.submissions.count() == 0
        type_pk = event.submission_types.first().pk

    response = orga_client.post(
        event.orga_urls.new_submission,
        data={
            'abstract': 'abstract',
            'content_locale': 'en',
            'description': 'description',
            'duration': '',
            'slot_count': 1,
            'notes': 'notes',
            'internal_notes': 'internal_notes',
            'speaker': 'foo@bar.com',
            'speaker_name': 'Foo Speaker',
            'title': 'title',
            'submission_type': type_pk,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert event.submissions.count() == 1
        sub = event.submissions.first()
        assert sub.title == 'title'
        assert sub.speakers.count() == 1


@pytest.mark.django_db
def test_orga_can_edit_submission(orga_client, event, accepted_submission):
    event.settings.present_multiple_times = True
    with scope(event=event):
        assert event.submissions.count() == 1
        assert accepted_submission.slots.count() == 1

    response = orga_client.post(
        accepted_submission.orga_urls.base,
        data={
            'abstract': 'abstract',
            'content_locale': 'en',
            'description': 'description',
            'duration': '',
            'slot_count': 2,
            'notes': 'notes',
            'speaker': 'foo@bar.com',
            'speaker_name': 'Foo Speaker',
            'title': 'title',
            'submission_type': accepted_submission.submission_type.pk,
            'resource-TOTAL_FORMS': 0,
            'resource-INITIAL_FORMS': 0,
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
def test_orga_can_edit_submission_duration(orga_client, event, accepted_submission):
    with scope(event=event):
        slot = accepted_submission.slots.filter(schedule=event.wip_schedule).first()
        slot.start = now()
        slot.end = slot.start + timedelta(minutes=accepted_submission.get_duration())
        slot.save()
        assert slot.duration == accepted_submission.get_duration()

    response = orga_client.post(
        accepted_submission.orga_urls.base,
        data={
            'abstract': 'abstract',
            'content_locale': 'en',
            'description': 'description',
            'slot_count': 2,
            'notes': 'notes',
            'speaker': 'foo@bar.com',
            'speaker_name': 'Foo Speaker',
            'duration': 123,
            'title': 'title',
            'submission_type': accepted_submission.submission_type.pk,
            'resource-TOTAL_FORMS': 0,
            'resource-INITIAL_FORMS': 0,
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
