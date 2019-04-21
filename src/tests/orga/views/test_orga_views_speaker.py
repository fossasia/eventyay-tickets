import pytest


@pytest.mark.django_db
def test_orga_can_access_speakers_list(orga_client, speaker, event, submission):
    response = orga_client.get(event.orga_urls.speakers, follow=True)
    assert response.status_code == 200
    assert speaker.name in response.content.decode()


@pytest.mark.django_db
def test_orga_can_access_speaker_page(orga_client, speaker, event, submission):
    response = orga_client.get(speaker.event_profile(event).orga_urls.base, follow=True)
    assert response.status_code == 200
    assert speaker.name in response.content.decode()


@pytest.mark.django_db
def test_orga_can_change_speaker_password(orga_client, speaker, event, submission):
    assert not speaker.pw_reset_token
    response = orga_client.post(
        speaker.event_profile(event).orga_urls.password_reset, follow=True
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.pw_reset_token


@pytest.mark.django_db
def test_reviewer_can_access_speaker_page(review_client, speaker, event, submission):
    response = review_client.get(
        speaker.event_profile(event).orga_urls.base, follow=True
    )
    assert response.status_code == 200
    assert speaker.name in response.content.decode()


@pytest.mark.django_db
def test_reviewer_cannot_change_speaker_password(
    review_client, speaker, event, submission
):
    assert not speaker.pw_reset_token
    response = review_client.post(
        speaker.event_profile(event).orga_urls.password_reset, follow=True
    )
    assert response.status_code == 404
    speaker.refresh_from_db()
    assert not speaker.pw_reset_token


@pytest.mark.django_db
def test_reviewer_can_access_speaker_page_with_deleted_submission(
    review_client, other_speaker, event, deleted_submission
):
    assert event.submissions.all().count() == 0
    assert event.submissions(manager='all_objects').count() == 1
    response = review_client.get(
        other_speaker.event_profile(event).orga_urls.base, follow=True
    )
    assert response.status_code == 200
    assert other_speaker.name in response.content.decode()


@pytest.mark.django_db
def test_orga_can_edit_speaker(orga_client, speaker, event, submission):
    response = orga_client.post(
        speaker.event_profile(event).orga_urls.base,
        data={
            'name': 'BESTSPEAKAR',
            'biography': 'I rule!',
            'email': 'foo@foooobar.de',
        },
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.name == 'BESTSPEAKAR', response.content.decode()
    assert speaker.email == 'foo@foooobar.de'


@pytest.mark.django_db
def test_orga_cant_assign_duplicate_address(
    orga_client, speaker, event, submission, other_speaker
):
    event.settings.cfp_request_availabilities = False
    response = orga_client.post(
        speaker.event_profile(event).orga_urls.base,
        data={
            'name': 'BESTSPEAKAR',
            'biography': 'I rule!',
            'email': other_speaker.email,
        },
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
        speaker.profiles.first().orga_urls.toggle_arrived, follow=True
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.profiles.first().has_arrived is True
    assert speaker.logged_actions().count() == logs + 1
    response = orga_client.get(
        speaker.profiles.first().orga_urls.toggle_arrived + '?from=list', follow=True
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.profiles.first().has_arrived is False
    assert speaker.logged_actions().count() == logs + 2


@pytest.mark.django_db
def test_reviewer_cannot_edit_speaker(review_client, speaker, event, submission):
    response = review_client.post(
        speaker.event_profile(event).orga_urls.base,
        data={'name': 'BESTSPEAKAR', 'biography': 'I rule!'},
        follow=True,
    )
    assert response.status_code == 200
    speaker.refresh_from_db()
    assert speaker.name != 'BESTSPEAKAR', response.content.decode()


@pytest.mark.django_db
def test_orga_can_create_speaker_information(orga_client, event):
    assert event.information.all().count() == 0
    orga_client.post(
        event.orga_urls.new_information,
        data={
            'title_0': 'Test Information',
            'text_0': 'Very Important!!!',
            'include_submitters': 'on',
        },
        follow=True,
    )
    assert event.information.all().count() == 1


@pytest.mark.django_db
def test_orga_cant_create_illogical_speaker_information(orga_client, event):
    assert event.information.all().count() == 0
    orga_client.post(
        event.orga_urls.new_information,
        data={
            'title_0': 'Test Information',
            'text_0': 'Very Important!!!',
            'include_submitters': 'on',
            'exclude_unconfirmed': 'on',
        },
        follow=True,
    )
    assert event.information.all().count() == 0


@pytest.mark.django_db
def test_orga_can_edit_speaker_information(orga_client, event, information):
    orga_client.post(
        information.orga_urls.edit,
        data={
            'title_0': 'Banana banana',
            'text_0': 'Very Important!!!',
            'include_submitters': 'on',
        },
        follow=True,
    )
    information.refresh_from_db()
    assert str(information.title) == 'Banana banana'


@pytest.mark.django_db
def test_reviewer_cant_edit_speaker_information(review_client, event, information):
    review_client.post(
        information.orga_urls.edit,
        data={
            'title_0': 'Banana banana',
            'text_0': 'Very Important!!!',
            'include_submitters': 'on',
            'exclude_unconfirmed': 'on',
        },
        follow=True,
    )
    information.refresh_from_db()
    assert str(information.title) != 'Banana banana'


@pytest.mark.django_db
def test_orga_can_delete_speaker_information(orga_client, event, information):
    assert event.information.all().count() == 1
    orga_client.post(information.orga_urls.delete, follow=True)
    assert event.information.all().count() == 0
