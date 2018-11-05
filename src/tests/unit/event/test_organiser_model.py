import pytest

from pretalx.event.models import Event


@pytest.mark.django_db
def test_shred_used_event(resource, answered_choice_question, personal_answer, rejected_submission, deleted_submission, mail, sent_mail, room_availability, slot, unreleased_slot, past_slot, feedback, canceled_talk, review, information, other_event):
    assert Event.objects.count() == 2
    rejected_submission.event.organiser.shred()
    assert Event.objects.count() == 1
