import pytest


@pytest.mark.django_db
def test_can_see_schedule(client, event, slot):
    del event.current_schedule
    response = client.get(event.urls.schedule, follow=True)
    assert event.schedules.count() == 2
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_can_see_talk(client, event, slot):
    response = client.get(slot.submission.urls.public, follow=True)
    assert event.schedules.count() == 2
    assert response.status_code == 200
    assert slot.submission.title in response.content.decode()


@pytest.mark.django_db
def test_cannot_see_nonpublic_talk(client, event, slot):
    event.is_public = False
    event.save()
    response = client.get(slot.submission.urls.public, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_cannot_see_other_events_talk(client, event, slot, other_event):
    response = client.get(slot.submission.urls.public.replace(event.slug, other_event.slug), follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_event_talk_visiblity_submitted(client, event, submission):
    response = client.get(submission.urls.public, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_event_talk_visiblity_accepted(client, event, slot, accepted_submission):
    response = client.get(accepted_submission.urls.public, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_event_talk_visiblity_confirmed(client, event, slot, confirmed_submission):
    response = client.get(confirmed_submission.urls.public, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_event_talk_visiblity_canceled(client, event, slot, canceled_submission):
    response = client.get(canceled_submission.urls.public, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_event_talk_visiblity_withdrawn(client, event, slot, withdrawn_submission):
    response = client.get(withdrawn_submission.urls.public, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_talk_speaker_other_talks(client, event, speaker, slot, other_slot, other_submission):
    other_submission.speakers.add(speaker)
    response = client.get(other_submission.urls.public, follow=True)

    assert response.context['speakers']
    assert len(response.context['speakers'][0].other_talks) == 0
    assert len(response.context['speakers'][1].other_talks) == 1
    assert response.context['speakers'][1].other_talks[0].submission.title == speaker.submissions.first().title
