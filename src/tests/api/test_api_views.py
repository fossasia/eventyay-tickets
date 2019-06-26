import json

import pytest
from django_scopes import scope


@pytest.mark.django_db
def test_api_user_endpoint(orga_client, room):
    response = orga_client.get('/api/me', follow=True)
    assert response.status_code == 200
    content = json.loads(response.content.decode())
    assert set(content.keys()) == {'name', 'email', 'locale', 'timezone'}


@pytest.mark.django_db
def test_can_only_see_public_events(client, event, other_event):
    other_event.is_public = False
    other_event.save()
    assert event.is_public
    assert not other_event.is_public

    response = client.get('/api/events', follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content) == 1, content
    assert content[0]['name']['en'] == event.name


@pytest.mark.django_db
def test_orga_can_see_nonpublic_events(orga_client, event, other_event):
    event.is_public = False
    event.save()
    assert not event.is_public
    assert other_event.is_public

    response = orga_client.get('/api/events', follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content) == 2, content
    assert content[0]['name']['en'] == event.name


@pytest.mark.django_db
def test_can_only_see_public_submissions(
    client, slot, accepted_submission, rejected_submission, submission
):
    response = client.get(submission.event.api_urls.submissions, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1
    assert content['results'][0]['title'] == slot.submission.title


@pytest.mark.django_db
def test_can_only_see_public_submissions_if_public_schedule(
    client, slot, accepted_submission, rejected_submission, submission, answer
):
    submission.event.settings.set('show_schedule', False)
    response = client.get(submission.event.api_urls.submissions, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 0
    assert all(submission['answers'] == [] for submission in content['results'])


@pytest.mark.django_db
def test_orga_can_see_all_submissions(
    orga_client, slot, accepted_submission, rejected_submission, submission, answer
):
    response = orga_client.get(submission.event.api_urls.submissions, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 4
    assert content['results'][0]['title'] == slot.submission.title
    assert any(submission['answers'] == [] for submission in content['results'])
    assert any(submission['answers'] != [] for submission in content['results'])


@pytest.mark.django_db
def test_orga_can_see_all_submissions_even_nonpublic(
    orga_client, slot, accepted_submission, rejected_submission, submission
):
    submission.event.settings.set('show_schedule', False)
    response = orga_client.get(submission.event.api_urls.submissions, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 4
    assert content['results'][0]['title'] == slot.submission.title


@pytest.mark.django_db
def test_only_see_talks_when_a_release_exists(
    orga_client, confirmed_submission, rejected_submission, submission
):
    response = orga_client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert content['count'] == 0


@pytest.mark.django_db
def test_can_only_see_public_talks(
    client, slot, accepted_submission, rejected_submission, submission
):
    response = client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1
    assert content['results'][0]['title'] == slot.submission.title


@pytest.mark.django_db
def test_can_only_see_public_talks_if_public_schedule(
    client, slot, accepted_submission, rejected_submission, submission
):
    submission.event.settings.set('show_schedule', False)
    response = client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 0


@pytest.mark.django_db
def test_orga_can_see_all_talks(
    orga_client, slot, accepted_submission, rejected_submission, submission
):
    response = orga_client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1
    assert content['results'][0]['title'] == slot.submission.title


@pytest.mark.django_db
def test_orga_can_see_all_talks_even_nonpublic(
    orga_client, slot, accepted_submission, rejected_submission, submission
):
    submission.event.settings.set('show_schedule', False)
    response = orga_client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1
    assert content['results'][0]['title'] == slot.submission.title


@pytest.mark.django_db
def test_user_can_see_schedule(client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1


@pytest.mark.django_db
def test_user_cannot_see_wip_schedule(client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules + 'wip', follow=True)
    json.loads(response.content.decode())
    assert response.status_code == 404


@pytest.mark.django_db
def test_user_cannot_see_schedule_if_not_public(client, slot, event):
    slot.submission.event.settings.set('show_schedule', False)
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 0


@pytest.mark.django_db
def test_orga_can_see_schedule(orga_client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = orga_client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 2


@pytest.mark.django_db
def test_orga_can_see_wip_schedule(orga_client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = orga_client.get(
        slot.submission.event.api_urls.schedules + 'wip', follow=True
    )
    json.loads(response.content.decode())
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_can_see_current_schedule(orga_client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = orga_client.get(
        slot.submission.event.api_urls.schedules + 'latest', follow=True
    )
    json.loads(response.content.decode())
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_orga_cannot_see_schedule_even_if_not_public(orga_client, slot, event):
    slot.submission.event.settings.set('show_schedule', False)
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = orga_client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 2


@pytest.mark.django_db
def test_can_only_see_public_speakers(
    client,
    slot,
    accepted_submission,
    rejected_submission,
    submission,
    impersonal_answer,
    event,
):
    response = client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1
    with scope(event=event):
        assert content['results'][0]['name'] == accepted_submission.speakers.first().name
    assert set(content['results'][0].keys()) == {
        'name',
        'code',
        'biography',
        'submissions',
        'avatar',
    }


@pytest.mark.django_db
def test_can_only_see_public_speakerss_if_public_schedule(
    client, slot, accepted_submission, rejected_submission, submission
):
    submission.event.settings.set('show_schedule', False)
    response = client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 0


@pytest.mark.django_db
def test_orga_can_see_all_speakers(
    orga_client,
    slot,
    accepted_submission,
    rejected_submission,
    submission,
    impersonal_answer,
):
    response = orga_client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 2
    assert set(content['results'][0].keys()) == {
        'name',
        'code',
        'email',
        'biography',
        'submissions',
        'answers',
        'avatar',
        'availabilities',
    }
    assert set(content['results'][0]['answers'][0].keys()) == {
        'answer',
        'answer_file',
        'person',
        'question',
        'submission',
        'options',
        'id',
    }


@pytest.mark.django_db
def test_orga_can_see_all_speakers_with_limit_and_offset(
    orga_client,
    slot,
    accepted_submission,
    rejected_submission,
    submission,
    impersonal_answer,
):
    response = orga_client.get(submission.event.api_urls.speakers + '?limit=1', follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 2
    assert 'offset=1' in content['next']


@pytest.mark.django_db
def test_reviewer_cannot_see_speakers(
    review_client,
    slot,
    accepted_submission,
    rejected_submission,
    submission,
    impersonal_answer,
    event,
):
    with scope(event=event):
        submission.event.active_review_phase.can_see_speaker_names = False
        submission.event.active_review_phase.save()
    response = review_client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1  # can see the slot's speaker, but not the other submissions'


@pytest.mark.django_db
def test_orga_can_see_all_speakers_even_nonpublic(
    orga_client, slot, accepted_submission, rejected_submission, submission
):
    submission.event.settings.set('show_schedule', False)
    response = orga_client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 2


@pytest.mark.django_db
def test_orga_speakers_with_multiple_talks_are_not_duplicated(
    client, speaker, slot, other_slot, accepted_submission, other_accepted_submission
):
    other_accepted_submission.speakers.add(accepted_submission.speakers.first())
    response = client.get(accepted_submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 2


@pytest.mark.django_db
def test_anon_cannot_see_reviews(client, event, review):
    response = client.get(event.api_urls.reviews, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content['results']) == 0, content


@pytest.mark.django_db
def test_orga_can_see_reviews(orga_client, event, review):
    response = orga_client.get(event.api_urls.reviews, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content['results']) == 1


@pytest.mark.django_db
def test_orga_cannot_see_reviews_of_deleted_submission(orga_client, event, review):
    review.submission.state = 'deleted'
    review.submission.save()
    response = orga_client.get(event.api_urls.reviews, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content['results']) == 0


@pytest.mark.django_db
def test_reviewer_can_see_reviews(review_client, event, review, other_review):
    response = review_client.get(event.api_urls.reviews, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content['results']) == 2, content


@pytest.mark.django_db
def test_reviewer_can_filter_by_submission(review_client, event, review, other_review):
    response = review_client.get(
        event.api_urls.reviews + f'?submission__code={review.submission.code}',
        follow=True,
    )
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content['results']) == 1, content


@pytest.mark.django_db
def test_reviewer_cannot_see_review_to_own_talk(
    review_user, review_client, event, review, other_review
):
    other_review.submission.speakers.add(review_user)
    response = review_client.get(event.api_urls.reviews, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert len(content['results']) == 1, content


@pytest.mark.django_db
def test_not_everybody_can_see_rooms(client, room):
    response = client.get(room.event.api_urls.rooms, follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content['results']) == 0, content


@pytest.mark.django_db
def test_everybody_can_see_published_rooms(client, room, slot):
    room.event.is_public = True
    room.event.save()
    response = client.get(room.event.api_urls.rooms, follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content['results']) == 1, content


@pytest.mark.django_db
def test_orga_can_see_room_speaker_info(orga_client, room):
    response = orga_client.get(room.event.api_urls.rooms, follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert len(content['results']) == 1, content
    assert 'speaker_info' in content['results'][0]
