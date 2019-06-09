from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scope

from pretalx.schedule.models import TalkSlot


@pytest.mark.django_db()
def test_can_create_feedback(django_assert_num_queries, past_slot, client, event):
    with scope(event=event):
        assert past_slot.submission.speakers.count() == 1
    with django_assert_num_queries(53):
        response = client.post(
            past_slot.submission.urls.feedback, {'review': 'cool!'}, follow=True
        )
    assert response.status_code == 200
    with scope(event=event):
        assert past_slot.submission.feedback.first().review == 'cool!'
        assert (
            past_slot.submission.feedback.first().speaker
            == past_slot.submission.speakers.first()
        )
        assert past_slot.submission.title in str(past_slot.submission.feedback.first())


@pytest.mark.django_db()
def test_can_create_feedback_for_multiple_speakers(
    django_assert_num_queries, past_slot, client, other_speaker, speaker, event
):
    with scope(event=event):
        past_slot.submission.speakers.add(other_speaker)
        past_slot.submission.speakers.add(speaker)
        assert past_slot.submission.speakers.count() == 2
    with django_assert_num_queries(55):
        response = client.post(
            past_slot.submission.urls.feedback, {'review': 'cool!'}, follow=True
        )
    assert response.status_code == 200
    with scope(event=event):
        assert past_slot.submission.feedback.first().review == 'cool!'
        assert not past_slot.submission.feedback.first().speaker
        assert past_slot.submission.title in str(past_slot.submission.feedback.first())


@pytest.mark.django_db()
def test_cannot_create_feedback_before_talk(django_assert_num_queries, slot, client, event):
    _now = now()
    with scope(event=event):
        TalkSlot.objects.filter(submission__event=slot.event).update(
            start=_now + timedelta(minutes=30),
            end=_now + timedelta(minutes=60),
        )
    with django_assert_num_queries(23):
        response = client.post(
            slot.submission.urls.feedback, {'review': 'cool!'}, follow=True
        )
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.feedback.count() == 0
        assert slot.submission.speakers.count() == 1


@pytest.mark.django_db()
def test_can_see_feedback(django_assert_num_queries, feedback, client):
    client.force_login(feedback.talk.speakers.first())
    with django_assert_num_queries(24):
        response = client.get(feedback.talk.urls.feedback)
    assert response.status_code == 200
    assert feedback.review in response.content.decode()


@pytest.mark.django_db()
def test_can_see_feedback_form(django_assert_num_queries, past_slot, client):
    with django_assert_num_queries(23):
        response = client.get(past_slot.submission.urls.feedback, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db()
def test_cannot_see_feedback_form_before_talk(django_assert_num_queries, slot, client):
    with django_assert_num_queries(25):
        response = client.get(slot.submission.urls.feedback, follow=True)
    assert response.status_code == 200
