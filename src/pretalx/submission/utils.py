from django.db import transaction
from django_scopes import scopes_disabled

from pretalx.event.models import Event
from pretalx.submission.models import Submission


@scopes_disabled()
@transaction.atomic
def move_submission(code, new_event, copy=False):
    """Caution! Does not include.

    - submission type mapping (resets to default)
    - questions with options (choice/multiple choice)
    - other questions only if they are an exact string match
    - tags
    - tracks
    - review scores, presumably

    Set copy=True to not delete the proposal in the old event.
    """
    submission = Submission.objects.get(code__iexact=code)
    old_event = submission.event
    new_event = Event.objects.get(slug__iexact=new_event)

    speaker_questions = {
        str(q.question): q for q in new_event.questions.all().filter(target="speaker")
    }
    submission_questions = {
        str(q.question): q
        for q in new_event.questions.all().filter(target="submission")
    }

    if copy:
        submission.id = None
        submission.code += "C"
        submission.review_code = None
    submission.event = new_event
    submission.submission_type = new_event.cfp.default_type
    submission.save()

    for answer in (
        submission.answers.all()
        .filter(question__event=old_event)
        .select_related("question")
    ):
        other_question = submission_questions.get(str(answer.question.question))
        if other_question:
            answer.id = None
            answer.question = other_question
            answer.save()

    for speaker in submission.speakers.all():
        if not speaker.profiles.filter(event=new_event).exists():
            old_profile = speaker.event_profile(old_event)
            old_profile.pk = None
            old_profile.event = new_event
            old_profile.save()
        for answer in (
            speaker.answers.all()
            .filter(question__event=old_event)
            .select_related("question")
        ):
            other_question = speaker_questions.get(str(answer.question.question))
            if other_question:
                answer.id = None
                answer.question = other_question
                answer.save()
