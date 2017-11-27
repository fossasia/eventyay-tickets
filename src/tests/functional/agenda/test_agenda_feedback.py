import pytest


@pytest.mark.django_db()
def test_can_create_feedback(past_slot, client):
    response = client.post(past_slot.submission.urls.feedback, {'review': 'cool!'}, follow=True)
    assert past_slot.submission.speakers.count() == 1
    assert response.status_code == 200
    assert past_slot.submission.feedback.first().review == 'cool!'
    assert past_slot.submission.feedback.first().speaker == past_slot.submission.speakers.first()


@pytest.mark.django_db()
def test_cannot_create_feedback_before_talk(slot, client):
    response = client.post(slot.submission.urls.feedback, {'review': 'cool!'}, follow=True)
    assert slot.submission.speakers.count() == 1
    assert response.status_code == 404
    assert slot.submission.feedback.count() == 0


@pytest.mark.django_db()
def test_can_see_feedback(feedback, client):
    client.force_login(feedback.talk.speakers.first())
    response = client.get(feedback.talk.urls.feedback)
    assert response.status_code == 200
    assert feedback.review in response.content.decode()


@pytest.mark.django_db()
def test_can_see_feedback_form(past_slot, client):
    response = client.get(past_slot.submission.urls.feedback, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db()
def test_cannot_see_feedback_form_before_talk(slot, client):
    response = client.get(slot.submission.urls.feedback, follow=True)
    assert response.status_code == 404
