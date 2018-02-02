import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from pretalx.submission.models import Answer, AnswerOption


@pytest.mark.parametrize('target', ('submission', 'speaker'))
@pytest.mark.django_db
def test_missing_answers_submission_question(submission, target, question):
    assert question.missing_answers == 1
    question.target = target
    question.save()
    if target == 'submission':
        Answer.objects.create(answer='True', submission=submission, question=question)
    else:
        Answer.objects.create(answer='True', person=submission.speakers.first(), question=question)
    del(question.missing_answers)
    assert question.missing_answers == 0


@pytest.mark.django_db
def test_question_base_properties(submission, question):
    a = Answer.objects.create(answer='True', submission=submission, question=question)
    assert a.event == question.event


@pytest.mark.django_db
def test_question_grouped_answers_choice(submission, question):
    question.variant = 'multiple_choice'
    question.save()
    one = AnswerOption.objects.create(question=question, answer='1')
    two = AnswerOption.objects.create(question=question, answer='2')
    one.refresh_from_db()
    two.refresh_from_db()

    answers = [Answer.objects.create(submission=submission, question=question, answer='True') for _ in range(3)]
    answers[0].options.set([one])
    answers[1].options.set([two])
    answers[2].options.set([two])
    [a.save() for a in answers]

    assert list(question.grouped_answers) == [
        {'options': 2, 'options__answer': two.answer, 'count': 2},
        {'options': 1, 'options__answer': one.answer, 'count': 1},
    ]


@pytest.mark.django_db
def test_question_grouped_answers_file(submission, question):
    f = SimpleUploadedFile('testfile.txt', b'file_content')
    question.variant = 'file'
    question.save()
    [Answer.objects.create(submission=submission, question=question, answer='file://testfile.txt', answer_file=f) for _ in range(3)]

    assert len(question.grouped_answers) == 3
    assert all([a['count'] == 1 for a in question.grouped_answers])


@pytest.mark.django_db
def test_question_grouped_answers_other(submission, question):
    Answer.objects.create(submission=submission, question=question, answer='True')
    Answer.objects.create(submission=submission, question=question, answer='True')
    Answer.objects.create(submission=submission, question=question, answer='False')

    assert list(question.grouped_answers) == [
        {'answer': 'True', 'count': 2},
        {'answer': 'False', 'count': 1},
    ]
