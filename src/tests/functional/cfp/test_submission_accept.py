import pytest

from pretalx.submission.models import SubmissionStates


@pytest.mark.django_db
@pytest.mark.parametrize('request_availability', (True, False))
def test_submission_accept(speaker_client, submission, request_availability):
    submission.event.settings.cfp_request_availabilities = request_availability
    submission.state = SubmissionStates.ACCEPTED
    submission.save()

    response = speaker_client.post(submission.urls.confirm, follow=True)
    submission.refresh_from_db()

    assert response.status_code == 200
    assert submission.state == SubmissionStates.CONFIRMED


@pytest.mark.django_db
def test_submission_accept_with_missing_availability(speaker_client, submission):
    submission.event.settings.cfp_request_availabilities = True
    submission.event.settings.cfp_require_availabilities = True
    submission.state = SubmissionStates.ACCEPTED
    submission.save()

    response = speaker_client.post(submission.urls.confirm, follow=True)
    submission.refresh_from_db()

    assert response.status_code == 200
    assert submission.state == SubmissionStates.ACCEPTED


@pytest.mark.django_db
def test_submission_accept_nologin(client, submission):
    submission.state = SubmissionStates.ACCEPTED
    submission.save()

    response = client.post(submission.urls.confirm, follow=True)
    submission.refresh_from_db()

    assert response.status_code == 200
    assert response.redirect_chain[-1][1] == 302
    assert 'login/?next=' in response.redirect_chain[-1][0]
    assert submission.state == SubmissionStates.ACCEPTED


@pytest.mark.django_db
def test_submission_accept_wrong_code(client, submission):
    submission.state = SubmissionStates.ACCEPTED
    submission.save()

    assert submission.code in submission.urls.confirm
    response = client.post(
        submission.urls.confirm.replace(submission.code, "foo"), follow=True
    )

    assert response.status_code == 200
    assert response.redirect_chain[-1][1] == 302
    assert 'login/?next=' in response.redirect_chain[-1][0]


@pytest.mark.django_db
def test_submission_withdraw(speaker_client, submission):
    submission.state = SubmissionStates.SUBMITTED
    submission.save()

    response = speaker_client.post(submission.urls.withdraw, follow=True)
    assert response.status_code == 200
    submission.refresh_from_db()
    assert submission.state == SubmissionStates.WITHDRAWN


@pytest.mark.django_db
def test_submission_withdraw_if_not_accepted(speaker_client, submission):
    submission.accept()

    response = speaker_client.post(submission.urls.withdraw, follow=True)
    assert response.status_code == 200
    submission.refresh_from_db()
    assert submission.state != SubmissionStates.WITHDRAWN
