import pytest


@pytest.mark.django_db
def test_delete_submission_type(orga_client, submission_type, default_submission_type):
    assert default_submission_type.event.submission_types.count() == 2
    response = orga_client.get(submission_type.urls.delete, follow=True)
    assert response.status_code == 200
    assert default_submission_type.event.submission_types.count() == 1


@pytest.mark.django_db
def test_delete_last_submission_type(orga_client, event):
    submission_type = event.cfp.default_type
    assert submission_type.event.submission_types.count() == 1
    response = orga_client.get(submission_type.urls.delete, follow=True)
    assert response.status_code == 200
    assert submission_type.event.submission_types.count() == 1


@pytest.mark.django_db
def test_delete_default_submission_type(orga_client, submission_type, default_submission_type):
    assert default_submission_type.event.submission_types.count() == 2
    response = orga_client.get(default_submission_type.urls.delete, follow=True)
    assert response.status_code == 200
    assert default_submission_type.event.submission_types.count() == 2


@pytest.mark.django_db
def test_delete_question(orga_client, event, question):
    assert event.questions.count() == 1
    response = orga_client.get(question.urls.delete, follow=True)
    assert response.status_code == 200
    assert event.questions.count() == 0


@pytest.mark.django_db
def test_cannot_delete_answered_question(orga_client, event, question, answer):
    assert event.questions.count() == 1
    response = orga_client.get(question.urls.delete, follow=True)
    assert response.status_code == 200
    assert event.questions.count() == 1
