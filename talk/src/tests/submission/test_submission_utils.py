import pytest
from django_scopes import scopes_disabled

from pretalx.submission.utils import move_submission


@pytest.mark.django_db
@scopes_disabled()
def test_simple_submission_move(other_event, submission):
    assert submission.event != other_event
    assert not submission.speakers.first().profiles.filter(event=other_event)

    move_submission(submission.code, other_event.slug)
    submission.refresh_from_db()

    assert submission.event == other_event
    assert submission.speakers.first().profiles.filter(event=other_event)


@pytest.mark.django_db
@scopes_disabled()
def test_simple_submission_move_with_questions(
    other_event, submission, answer, speaker_answer
):
    # set up matching questions
    answer.question.id = None
    answer.question.event = other_event
    answer.question.save()
    speaker_answer.question.id = None
    speaker_answer.question.event = other_event
    speaker_answer.question.save()
    assert other_event.questions.all().count() == 2

    assert submission.event != other_event
    assert not submission.speakers.first().profiles.filter(event=other_event)

    move_submission(submission.code, other_event.slug)
    submission.refresh_from_db()

    assert submission.event == other_event
    assert submission.speakers.first().profiles.filter(event=other_event)
    assert submission.answers.all().filter(question__event=other_event)
    assert submission.speakers.first().answers.all().filter(question__event=other_event)
