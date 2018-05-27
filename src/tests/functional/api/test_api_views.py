import json

import pytest


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
def test_can_only_see_public_submissions(client, slot, accepted_submission, rejected_submission, submission):
    response = client.get(submission.event.api_urls.submissions, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1
    assert content['results'][0]['title'] == slot.submission.title


@pytest.mark.django_db
def test_can_only_see_public_submissions_if_public_schedule(client, slot, accepted_submission, rejected_submission, submission):
    submission.event.settings.set('show_schedule', False)
    response = client.get(submission.event.api_urls.submissions, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 0


@pytest.mark.django_db
def test_orga_can_see_all_submissions(orga_client, slot, accepted_submission, rejected_submission, submission):
    response = orga_client.get(submission.event.api_urls.submissions, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 4
    assert content['results'][0]['title'] == slot.submission.title


@pytest.mark.django_db
def test_orga_can_see_all_submissions_even_nonpublic(orga_client, slot, accepted_submission, rejected_submission, submission):
    submission.event.settings.set('show_schedule', False)
    response = orga_client.get(submission.event.api_urls.submissions, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 4
    assert content['results'][0]['title'] == slot.submission.title


@pytest.mark.django_db
def test_only_see_talks_when_a_release_exists(orga_client, confirmed_submission, rejected_submission, submission):
    response = orga_client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())
    assert response.status_code == 200
    assert content['count'] == 0


@pytest.mark.django_db
def test_can_only_see_public_talks(client, slot, accepted_submission, rejected_submission, submission):
    response = client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1
    assert content['results'][0]['title'] == slot.submission.title


@pytest.mark.django_db
def test_can_only_see_public_talks_if_public_schedule(client, slot, accepted_submission, rejected_submission, submission):
    submission.event.settings.set('show_schedule', False)
    response = client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 0


@pytest.mark.django_db
def test_orga_can_see_all_talks(orga_client, slot, accepted_submission, rejected_submission, submission):
    response = orga_client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1
    assert content['results'][0]['title'] == slot.submission.title


@pytest.mark.django_db
def test_orga_can_see_all_talks_even_nonpublic(orga_client, slot, accepted_submission, rejected_submission, submission):
    submission.event.settings.set('show_schedule', False)
    response = orga_client.get(submission.event.api_urls.talks, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1
    assert content['results'][0]['title'] == slot.submission.title


@pytest.mark.django_db
def test_user_can_see_schedule(client, slot):
    assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1


@pytest.mark.django_db
def test_user_cannot_see_wip_schedule(client, slot):
    assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules + '/wip', follow=True)
    json.loads(response.content.decode())
    assert response.status_code == 404


@pytest.mark.django_db
def test_user_cannot_see_schedule_if_not_public(client, slot):
    slot.submission.event.settings.set('show_schedule', False)
    assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 0


@pytest.mark.django_db
def test_orga_can_see_schedule(orga_client, slot):
    assert slot.submission.event.schedules.count() == 2
    response = orga_client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 2


@pytest.mark.django_db
def test_orga_can_see_wip_schedule(orga_client, slot):
    assert slot.submission.event.schedules.count() == 2
    response = orga_client.get(slot.submission.event.api_urls.schedules + '/wip', follow=True)
    json.loads(response.content.decode())
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_can_see_current_schedule(orga_client, slot):
    assert slot.submission.event.schedules.count() == 2
    response = orga_client.get(slot.submission.event.api_urls.schedules + '/latest', follow=True)
    json.loads(response.content.decode())
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_orga_cannot_see_schedule_even_if_not_public(orga_client, slot):
    slot.submission.event.settings.set('show_schedule', False)
    assert slot.submission.event.schedules.count() == 2
    response = orga_client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 2


@pytest.mark.django_db
def test_can_only_see_public_speakers(client, slot, accepted_submission, rejected_submission, submission, impersonal_answer):
    response = client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 1
    assert content['results'][0]['name'] == accepted_submission.speakers.first().name
    assert set(content['results'][0].keys()) == {'name', 'code', 'biography', 'submissions', 'avatar'}


@pytest.mark.django_db
def test_can_only_see_public_speakerss_if_public_schedule(client, slot, accepted_submission, rejected_submission, submission):
    submission.event.settings.set('show_schedule', False)
    response = client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 0


@pytest.mark.django_db
def test_orga_can_see_all_speakers(orga_client, slot, accepted_submission, rejected_submission, submission, impersonal_answer):
    response = orga_client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 2
    assert set(content['results'][0].keys()) == {'name', 'code', 'biography', 'submissions', 'answers', 'avatar'}
    assert set(content['results'][0]['answers'][0].keys()) == {'answer', 'answer_file', 'person', 'question', 'submission', 'options', 'id'}


@pytest.mark.django_db
def test_orga_can_see_all_speakers_even_nonpublic(orga_client, slot, accepted_submission, rejected_submission, submission):
    submission.event.settings.set('show_schedule', False)
    response = orga_client.get(submission.event.api_urls.speakers, follow=True)
    content = json.loads(response.content.decode())

    assert response.status_code == 200
    assert content['count'] == 2
