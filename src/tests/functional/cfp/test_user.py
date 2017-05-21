import pytest
from django.urls import reverse

from pretalx.submission.models import SubmissionStates


@pytest.mark.django_db
def test_can_see_submission_list(speaker_client, submission):
    response = speaker_client.get(
        reverse(f'cfp:event.user.submissions', kwargs={'event': submission.event.slug}),
        follow=True,
    )
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_can_see_submission(speaker_client, submission):
    response = speaker_client.get(
        reverse(f'cfp:event.user.submission.edit', kwargs={'event': submission.event.slug, 'id': submission.pk}),
        follow=True,
    )
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_can_confirm_submission(speaker_client, accepted_submission):
    response = speaker_client.get(
        reverse(f'cfp:event.user.submission.confirm', kwargs={'event': accepted_submission.event.slug, 'id': accepted_submission.pk}),
        follow=True,
    )
    accepted_submission.refresh_from_db()
    assert response.status_code == 200
    assert accepted_submission.state == SubmissionStates.CONFIRMED


@pytest.mark.django_db
def test_can_withdraw_submission(speaker_client, submission):
    response = speaker_client.get(
        reverse(f'cfp:event.user.submission.withdraw', kwargs={'event': submission.event.slug, 'id': submission.pk}),
        follow=True,
    )
    submission.refresh_from_db()
    assert response.status_code == 200
    assert submission.state == SubmissionStates.WITHDRAWN


@pytest.mark.django_db
def test_cannot_withdraw_accepted_submission(speaker_client, accepted_submission):
    response = speaker_client.get(
        reverse(f'cfp:event.user.submission.withdraw', kwargs={'event': accepted_submission.event.slug, 'id': accepted_submission.pk}),
        follow=True,
    )
    accepted_submission.refresh_from_db()
    assert response.status_code == 200
    assert accepted_submission.state == SubmissionStates.ACCEPTED
