import pytest

from pretalx.event.models import Event
from pretalx.submission.models import Question


@pytest.mark.django_db
def test_edit_cfp(orga_client, event):
    assert event.settings.review_min_score == 0
    assert event.settings.review_max_score == 1
    assert event.settings.review_score_names is None
    response = orga_client.post(
        event.cfp.urls.edit_text,
        {
            'headline_0': 'new headline', 'text_0': '', 'deadline': '2000-10-10 20:20',
            'settings-review_min_score': '0',
            'settings-review_max_score': '2',
            'settings-review_score_name_0': 'OK',
            'settings-review_score_name_1': 'Want',
            'settings-review_score_name_2': 'Super',
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    assert str(event.cfp.headline) == 'new headline'
    assert response.status_code == 200
    assert event.settings.review_min_score == 0
    assert event.settings.review_max_score == 2


@pytest.mark.django_db
def test_edit_cfp_invalid(orga_client, event):
    assert event.settings.review_min_score == 0
    assert event.settings.review_max_score == 1
    assert event.settings.review_score_names is None
    old_headline = event.cfp.headline or ''
    response = orga_client.post(
        event.cfp.urls.edit_text,
        {
            'headline_0': 'new headline', 'text_0': '', 'deadline': '2000-10-10 20:20',
            'settings-review_min_score': '2',
            'settings-review_max_score': '2',
            'settings-review_score_name_0': 'OK',
            'settings-review_score_name_1': 'Want',
            'settings-review_score_name_2': 'Super',
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    assert str(event.cfp.headline) == str(old_headline)
    assert response.status_code == 200
    assert event.settings.review_min_score == 0
    assert event.settings.review_max_score == 1


@pytest.mark.django_db
def test_make_submission_type_default(orga_client, submission_type, default_submission_type):
    assert default_submission_type.event.submission_types.count() == 2
    assert submission_type.event.cfp.default_type == default_submission_type
    response = orga_client.get(submission_type.urls.default, follow=True)
    assert response.status_code == 200
    assert default_submission_type.event.submission_types.count() == 2
    submission_type.event.cfp.refresh_from_db()
    assert submission_type.event.cfp.default_type == submission_type


@pytest.mark.django_db
def test_edit_submission_type(orga_client, submission_type):
    response = orga_client.post(
        submission_type.urls.edit,
        {'default_duration': 31, 'max_duration': 61, 'name_0': 'New Type!'},
        follow=True,
    )
    submission_type.refresh_from_db()
    assert response.status_code == 200
    assert submission_type.default_duration == 31
    assert submission_type.max_duration == 61
    assert str(submission_type.name) == 'New Type!'


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
def test_all_questions_in_list(orga_client, question, inactive_question, event):
    assert event.questions.count() == 1
    assert Question.all_objects.filter(event=event).count() == 2
    response = orga_client.get(event.cfp.urls.questions, follow=True)
    assert question.question in response.content.decode()
    assert inactive_question.question in response.content.decode()


@pytest.mark.django_db
def test_delete_question(orga_client, event, question):
    assert event.questions.count() == 1
    response = orga_client.get(question.urls.delete, follow=True)
    assert response.status_code == 200
    assert event.questions.count() == 0
    assert Question.all_objects.filter(event=event).count() == 0


@pytest.mark.django_db
def test_delete_inactive_question(orga_client, event, inactive_question):
    assert Question.all_objects.filter(event=event).count() == 1
    response = orga_client.get(inactive_question.urls.delete, follow=True)
    assert response.status_code == 200
    assert event.questions.count() == 0
    assert Question.all_objects.filter(event=event).count() == 0


@pytest.mark.django_db
def test_delete_choice_question(orga_client, event, choice_question):
    assert Question.all_objects.filter(event=event).count() == 1
    response = orga_client.get(choice_question.urls.delete, follow=True)
    assert response.status_code == 200
    assert event.questions.count() == 0
    assert Question.all_objects.filter(event=event).count() == 0


@pytest.mark.django_db
def test_cannot_delete_answered_question(orga_client, event, answered_choice_question):
    assert event.questions.count() == 1
    assert answered_choice_question.answers.count() == 1
    assert answered_choice_question.options.count() == 3
    response = orga_client.get(answered_choice_question.urls.delete, follow=True)
    assert response.status_code == 200
    answered_choice_question = Question.all_objects.get(pk=answered_choice_question.pk)
    assert answered_choice_question
    assert not answered_choice_question.active
    assert event.questions.count() == 0
    assert answered_choice_question.answers.count() == 1
    assert answered_choice_question.options.count() == 3


@pytest.mark.django_db
def test_can_add_simple_question(orga_client, event):
    assert event.questions.count() == 0
    response = orga_client.post(
        event.cfp.urls.new_question,
        {
            'target': 'submission',
            'question_0': 'What is your name?',
            'variant': 'string',
            'active': True,
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
            'active': True,
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
            'active': True,
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
