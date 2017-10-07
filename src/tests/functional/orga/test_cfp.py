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


@pytest.mark.django_db
def test_can_add_simple_question(orga_client, event):
    assert event.questions.count() == 0
    response = orga_client.post(
        event.cfp.urls.new_question,
        {
            'target': 'submission',
            'question_0': 'What is your name?',
            'variant': 'string',
            'help_text_0': 'Answer if you want to reach the other side!',
        }, follow=True,
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.questions.count() == 1
    q = event.questions.first()
    assert str(q.question) == 'What is your name?'
    assert q.variant == 'string'


@pytest.mark.django_db
def test_can_add_choice_question(orga_client, event):
    assert event.questions.count() == 0
    response = orga_client.post(
        event.cfp.urls.new_question,
        {
            'target': 'submission',
            'question_0': 'Is it an African or a European swallow?',
            'variant': 'choices',
            'help_text_0': 'Answer if you want to reach the other side!',
            'form-TOTAL_FORMS': 2,
            'form-INITIAL_FORMS': 0,
            'form-0-id': '',
            'form-0-answer_0': 'African',
            'form-1-id': '',
            'form-1-answer_0': 'European',
            'form-2-id': '',
            'form-2-answer_0': '',
        }, follow=True,
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.questions.count() == 1
    q = event.questions.first()
    assert q.variant == 'choices'
    assert q.options.count() == 2


@pytest.mark.django_db
def test_can_edit_choice_question(orga_client, event, choice_question):
    count = choice_question.options.count()
    assert str(choice_question.options.first().answer) != 'African'
    response = orga_client.post(
        choice_question.urls.edit,
        {
            'target': 'submission',
            'question_0': 'Is it an African or a European swallow?',
            'variant': 'choices',
            'help_text_0': 'Answer if you want to reach the other side!',
            'form-TOTAL_FORMS': 3,
            'form-INITIAL_FORMS': 3,
            'form-0-id': choice_question.options.first().pk,
            'form-0-answer_0': 'African',
            'form-1-id': choice_question.options.last().pk,
            'form-1-answer_0': 'European',
            'form-2-id': choice_question.options.all()[1].pk,
            'form-2-answer_0': str(choice_question.options.all()[1].answer),
            'form-2-DELETE': 'on',
            'form-3-id': '',
            'form-3-answer_0': '',
        }, follow=True,
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.questions.count() == 1
    assert choice_question.variant == 'choices'
    assert choice_question.options.count() == count - 1
    assert str(choice_question.options.first().answer) == 'African'
