import pytest
from django.urls import reverse

from pretalx.submission.models import SubmissionStates


@pytest.mark.django_db
def test_can_see_submission_list(speaker_client, submission):
    response = speaker_client.get(
        submission.event.urls.user_submissions,
        follow=True,
    )
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_can_see_submission(speaker_client, submission):
    response = speaker_client.get(
        submission.urls.user_base,
        follow=True,
    )
    assert response.status_code == 200
    assert submission.title in response.content.decode()


@pytest.mark.django_db
def test_cannot_see_other_submission(speaker_client, other_submission):
    response = speaker_client.get(
        other_submission.urls.user_base,
        follow=True,
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_can_confirm_submission(speaker_client, accepted_submission):
    response = speaker_client.get(
        accepted_submission.urls.confirm,
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
        accepted_submission.urls.confirm,
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
        rejected_submission.urls.confirm,
        follow=True,
    )
    rejected_submission.refresh_from_db()
    assert response.status_code == 200
    assert rejected_submission.state == SubmissionStates.REJECTED


@pytest.mark.django_db
def test_can_withdraw_submission(speaker_client, submission):
    response = speaker_client.get(
        submission.urls.withdraw,
        follow=True,
    )
    submission.refresh_from_db()
    assert response.status_code == 200
    assert submission.state == SubmissionStates.WITHDRAWN


@pytest.mark.django_db
def test_cannot_withdraw_accepted_submission(speaker_client, accepted_submission):
    response = speaker_client.get(
        accepted_submission.urls.withdraw,
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
        submission.urls.user_base + '/',
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
        rejected_submission.urls.user_base,
        follow=True, data=data,
    )
    assert response.status_code == 200
    rejected_submission.refresh_from_db()
    assert rejected_submission.title == title


@pytest.mark.django_db
def test_can_edit_profile(speaker, event, speaker_client):
    response = speaker_client.post(
        event.urls.user,
        data={'name': 'Lady Imperator', 'biography': 'Ruling since forever.', 'form': 'profile'},
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.profiles.get(event=event).biography == 'Ruling since forever.'
    assert speaker.name == 'Lady Imperator'


@pytest.mark.django_db
def test_can_change_locale(multilingual_event, client):
    first_response = client.get(multilingual_event.urls.base, follow=True)
    assert 'submission' in first_response.content.decode()
    assert 'Einreichung' not in first_response.content.decode()
    second_response = client.get(
        reverse('cfp:locale.set', kwargs={'event': multilingual_event.slug}) + f'?locale=de&next=/{multilingual_event.slug}/',
        follow=True,
    )
    assert 'Einreichung' in second_response.content.decode()


@pytest.mark.django_db
def test_persists_changed_locale(multilingual_event, orga_user, orga_client):
    assert orga_user.locale == 'en'
    response = orga_client.get(
        reverse('cfp:locale.set', kwargs={'event': multilingual_event.slug}) + f'?locale=de&next=/{multilingual_event.slug}/',
        follow=True,
    )
    orga_user.refresh_from_db()
    assert response.status_code == 200
    assert orga_user.locale == 'de'
