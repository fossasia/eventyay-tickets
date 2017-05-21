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
def test_cannot_see_other_submission(speaker_client, other_submission):
    response = speaker_client.get(
        reverse(f'cfp:event.user.submission.edit', kwargs={'event': other_submission.event.slug, 'id': other_submission.pk}),
        follow=True,
    )
    assert response.status_code == 404


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
def test_can_reconfirm_submission(speaker_client, accepted_submission):
    accepted_submission.state = SubmissionStates.CONFIRMED
    accepted_submission.save()
    response = speaker_client.get(
        reverse(f'cfp:event.user.submission.confirm', kwargs={'event': accepted_submission.event.slug, 'id': accepted_submission.pk}),
        follow=True,
    )
    accepted_submission.refresh_from_db()
    assert response.status_code == 200
    assert accepted_submission.state == SubmissionStates.CONFIRMED


@pytest.mark.django_db
def test_cannot_confirm_rejected_submission(speaker_client, rejected_submission):
    rejected_submission.state = SubmissionStates.REJECTED
    rejected_submission.save()
    response = speaker_client.get(
        reverse(f'cfp:event.user.submission.confirm', kwargs={'event': rejected_submission.event.slug, 'id': rejected_submission.pk}),
        follow=True,
    )
    rejected_submission.refresh_from_db()
    assert response.status_code == 200
    assert rejected_submission.state == SubmissionStates.REJECTED


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


@pytest.mark.django_db
def test_can_edit_submission(speaker_client, submission):
    data = {
        'title': 'Ein ganz neuer Titel',
        'submission_type': submission.submission_type.pk,
        'content_locale': submission.content_locale,
        'description': submission.description,
        'abstract': submission.abstract,
        'notes': submission.notes,
    }
    response = speaker_client.post(
        reverse(f'cfp:event.user.submission.edit', kwargs={'event': submission.event.slug, 'id': submission.pk}),
        follow=True, data=data,
    )
    assert response.status_code == 200
    submission.refresh_from_db()
    assert submission.title == 'Ein ganz neuer Titel', response.content.decode()


@pytest.mark.django_db
def test_cannot_edit_rejected_submission(speaker_client, rejected_submission):
    title = rejected_submission.title
    data = {
        'title': 'Ein ganz neuer Titel',
        'submission_type': rejected_submission.submission_type.pk,
        'content_locale': rejected_submission.content_locale,
        'description': rejected_submission.description,
        'abstract': rejected_submission.abstract,
        'notes': rejected_submission.notes,
    }
    response = speaker_client.post(
        reverse(f'cfp:event.user.submission.edit', kwargs={'event': rejected_submission.event.slug, 'id': rejected_submission.pk}),
        follow=True, data=data,
    )
    assert response.status_code == 200
    rejected_submission.refresh_from_db()
    assert rejected_submission.title == title
