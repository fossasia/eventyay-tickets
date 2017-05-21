import pytest
from django.urls import reverse

from pretalx.submission.models import SubmissionStates


@pytest.mark.django_db
def test_accept_submission(orga_client, submission):
    assert submission.event.queued_mails.count() == 0
    assert submission.state == SubmissionStates.SUBMITTED

    response = orga_client.get(
        reverse(f'orga:submissions.accept', kwargs={'event': submission.event.slug, 'pk': submission.pk}),
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
        reverse(f'orga:submissions.reject', kwargs={'event': submission.event.slug, 'pk': submission.pk}),
        follow=True,
    )
    submission.refresh_from_db()

    assert response.status_code == 200
    assert submission.event.queued_mails.count() == 1
    assert submission.state == SubmissionStates.REJECTED
