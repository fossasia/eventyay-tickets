import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_orga_can_access_speakers_list(orga_client, speaker, event, submission):
    response = orga_client.get(reverse('orga:speakers.list', kwargs={'event': event.slug}), follow=True)
    assert response.status_code == 200
    assert speaker.name in response.content.decode()


@pytest.mark.django_db
def test_orga_can_access_speaker_page(orga_client, speaker, event, submission):
    response = orga_client.get(reverse('orga:speakers.view', kwargs={'event': event.slug, 'pk': speaker.pk}), follow=True)
    assert response.status_code == 200
    assert speaker.name in response.content.decode()


@pytest.mark.django_db
def test_reviewer_can_access_speaker_page(review_client, speaker, event, submission):
    response = review_client.get(reverse('orga:speakers.view', kwargs={'event': event.slug, 'pk': speaker.pk}), follow=True)
    assert response.status_code == 200
    assert speaker.name in response.content.decode()


@pytest.mark.django_db
def test_reviewer_can_access_speaker_page_with_deleted_submission(review_client, other_speaker, event, deleted_submission):
    response = review_client.get(reverse('orga:speakers.view', kwargs={'event': event.slug, 'pk': other_speaker.pk}), follow=True)
    assert response.status_code == 200
    assert other_speaker.name in response.content.decode()


@pytest.mark.django_db
def test_orga_can_edit_speaker(orga_client, speaker, event, submission):
    response = orga_client.post(
        reverse('orga:speakers.view', kwargs={'event': event.slug, 'pk': speaker.pk}),
        data={'name': 'BESTSPEAKAR', 'biography': 'I rule!', 'email': 'foo@foooobar.de'},
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.name == 'BESTSPEAKAR', response.content.decode()
    assert speaker.email == 'foo@foooobar.de'


@pytest.mark.django_db
def test_orga_cant_assign_duplicate_address(orga_client, speaker, event, submission, other_speaker):
    response = orga_client.post(
        reverse('orga:speakers.view', kwargs={'event': event.slug, 'pk': speaker.pk}),
        data={'name': 'BESTSPEAKAR', 'biography': 'I rule!', 'email': other_speaker.email},
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.name != 'BESTSPEAKAR', response.content.decode()
    assert speaker.email != other_speaker.email


@pytest.mark.django_db
def test_orga_can_edit_speaker_status(orga_client, speaker, event, submission):
    logs = speaker.logged_actions().count()
    assert speaker.profiles.first().has_arrived is False
    response = orga_client.get(
        reverse('orga:speakers.arrived', kwargs={'event': event.slug, 'pk': speaker.pk}),
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.profiles.first().has_arrived is True
    assert speaker.logged_actions().count() == logs + 1
    response = orga_client.get(
        reverse('orga:speakers.arrived', kwargs={'event': event.slug, 'pk': speaker.pk}) + '?from=list',
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.profiles.first().has_arrived is False
    assert speaker.logged_actions().count() == logs + 2


@pytest.mark.django_db
def test_reviewer_cannot_edit_speaker(review_client, speaker, event, submission):
    response = review_client.post(
        reverse('orga:speakers.view', kwargs={'event': event.slug, 'pk': speaker.pk}),
        data={'name': 'BESTSPEAKAR', 'biography': 'I rule!'},
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.name != 'BESTSPEAKAR', response.content.decode()
