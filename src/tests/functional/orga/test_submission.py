import pytest

from pretalx.submission.models import Submission, SubmissionStates


@pytest.mark.django_db
def test_orga_can_see_submissions(orga_client, event, submission):
    response = orga_client.get(event.orga_urls.submissions, follow=True)
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_orga_can_see_single_submission(orga_client, event, submission):
    response = orga_client.get(submission.orga_urls.base, follow=True)
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_orga_can_see_single_submission_feedback(orga_client, event, feedback):
    response = orga_client.get(feedback.talk.orga_urls.feedback, follow=True)
    assert response.status_code == 200
    assert feedback.review in response.content.decode()


@pytest.mark.django_db
def test_accept_submission(orga_client, submission):
    assert submission.event.queued_mails.count() == 0
    assert submission.state == SubmissionStates.SUBMITTED

    response = orga_client.get(
        submission.orga_urls.accept,
        follow=True,
    )
    submission.refresh_from_db()

    assert response.status_code == 200
    assert submission.event.queued_mails.count() == 1
    assert submission.state == SubmissionStates.ACCEPTED


@pytest.mark.django_db
def test_reject_submission(orga_client, submission):
    assert submission.event.queued_mails.count() == 0
    assert submission.state == SubmissionStates.SUBMITTED

    response = orga_client.get(
        submission.orga_urls.reject,
        follow=True,
    )
    submission.refresh_from_db()

    assert response.status_code == 200
    assert submission.event.queued_mails.count() == 1
    assert submission.state == SubmissionStates.REJECTED


@pytest.mark.django_db
def test_orga_can_confirm_submission(orga_client, accepted_submission):
    assert accepted_submission.state == SubmissionStates.ACCEPTED

    response = orga_client.get(
        accepted_submission.orga_urls.confirm,
        follow=True,
    )
    accepted_submission.refresh_from_db()

    assert response.status_code == 200
    assert accepted_submission.state == SubmissionStates.CONFIRMED


@pytest.mark.django_db
def test_orga_can_delete_submission(orga_client, submission):
    assert submission.state == SubmissionStates.SUBMITTED
    assert Submission.objects.count() == 1

    response = orga_client.get(
        submission.orga_urls.delete,
        follow=True,
    )
    submission.refresh_from_db()
    assert response.status_code == 200
    assert submission.state == SubmissionStates.SUBMITTED
    assert Submission.objects.count() == 1

    response = orga_client.post(
        submission.orga_urls.delete,
        follow=True,
    )
    assert response.status_code == 200
    assert Submission.objects.count() == 0
    assert Submission.deleted_objects.count() == 1
    assert Submission.deleted_objects.get(code=submission.code)


@pytest.mark.django_db
@pytest.mark.parametrize('user', ('NICK', 'EMAIL', 'NEW_EMAIL', 'OVERLAPPING_EMAIL'))
def test_orga_can_add_and_remove_speakers(orga_client, submission, other_orga_user, user):
    assert submission.speakers.count() == 1

    if user == 'NICK':  # TODO: add NICK and EMAIL
        user = other_orga_user.nick
        nick = other_orga_user.nick
    elif user == 'EMAIL':
        user = other_orga_user.email
        nick = other_orga_user.nick
    elif user == 'NEW_EMAIL':
        user = 'some_unused@mail.org'
        nick = 'some_unused'
    elif user == 'OVERLAPPING_EMAIL':
        user = f'{other_orga_user.nick}@mail.org'
        nick = None

    response = orga_client.post(submission.orga_urls.new_speaker, data={'nick': user}, follow=True)
    submission.refresh_from_db()

    assert submission.speakers.count() == 2
    assert response.status_code == 200

    if nick:
        response = orga_client.get(submission.orga_urls.delete_speaker, data={'nick': nick}, follow=True)
        submission.refresh_from_db()

        assert submission.speakers.count() == 1
        assert response.status_code == 200
    else:
        assert other_orga_user.nick != submission.speakers.last().nick
        assert submission.speakers.last().nick.startswith(other_orga_user.nick)
