import datetime

import pytest
from django.urls import reverse
from django.utils import formats


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
    content = response.content.decode()
    assert content.count(slot.submission.title) >= 2  # meta+h1
    assert slot.submission.abstract in content
    assert slot.submission.description in content
    assert formats.date_format(slot.start, 'Y-m-d, H:i') in content
    assert formats.date_format(slot.end, 'H:i') in content
    assert str(slot.room.name) in content
    assert 'fa-pencil' not in content  # edit btn
    assert 'fa-video-camera' not in content  # do not record


@pytest.mark.django_db
def test_cannot_see_new_talk(client, event, unreleased_slot):
    slot = unreleased_slot
    response = client.get(slot.submission.urls.public, follow=True)
    assert event.schedules.count() == 1
    assert response.status_code == 404


@pytest.mark.django_db
def test_orga_can_see_new_talk(orga_client, event, unreleased_slot):
    slot = unreleased_slot
    response = orga_client.get(slot.submission.urls.public, follow=True)
    assert event.schedules.count() == 1
    assert response.status_code == 200
    content = response.content.decode()
    assert content.count(slot.submission.title) >= 2  # meta+h1
    assert slot.submission.abstract in content
    assert slot.submission.description in content
    assert formats.date_format(slot.start, 'Y-m-d, H:i') in content
    assert formats.date_format(slot.end, 'H:i') in content
    assert str(slot.room.name) in content
    assert 'fa-pencil' not in content  # edit btn
    assert 'fa-video-camera' not in content  # do not record


@pytest.mark.django_db
def test_can_see_talk_edit_btn(orga_client, orga_user, event, slot):
    slot.submission.speakers.add(orga_user)
    response = orga_client.get(slot.submission.urls.public, follow=True)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'fa-pencil' in content  # edit btn
    assert 'fa-video-camera' not in content
    assert 'fa-comments' not in content


@pytest.mark.django_db
def test_can_see_talk_do_not_record(client, event, slot):
    slot.submission.do_not_record = True
    slot.submission.save()
    response = client.get(slot.submission.urls.public, follow=True)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'fa-pencil' not in content  # edit btn
    assert 'fa-video-camera' in content
    assert 'fa-comments' not in content


@pytest.mark.django_db
def test_can_see_talk_does_accept_feedback(client, event, slot):
    slot.start = (datetime.datetime.now() - datetime.timedelta(days=1))
    slot.end = slot.start + datetime.timedelta(hours=1)
    slot.save()
    response = client.get(slot.submission.urls.public, follow=True)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'fa-pencil' not in content  # edit btn
    assert 'fa-comments' in content
    assert 'fa-video-camera' not in content


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
    assert len(response.context['speakers']) == 2, response.context['speakers']
    speaker_response = [s for s in response.context['speakers'] if s.name == speaker.name][0]
    other_response = [s for s in response.context['speakers'] if s.name != speaker.name][0]
    assert len(speaker_response.other_talks) == 1
    assert len(other_response.other_talks) == 0
    assert speaker_response.other_talks[0].submission.title == speaker.submissions.first().title


@pytest.mark.django_db
def test_speaker_page(client, event, speaker, slot):
    response = client.get(reverse('agenda:speaker', kwargs={'code': speaker.code, 'event': event.slug}), follow=True)
    assert response.status_code == 200
    assert speaker.profiles.get(event=event).biography in response.content.decode()
