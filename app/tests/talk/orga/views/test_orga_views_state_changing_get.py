import pytest
from django.urls import reverse
from django_scopes import scope

from eventyay.base.models import Event, QueuedMail
from eventyay.base.models import TalkQuestion as Question


@pytest.mark.django_db
def test_get_does_not_toggle_schedule_visibility(orga_client, event):
    before = event.get_feature_flag('show_schedule')

    response = orga_client.get(event.orga_urls.toggle_schedule)

    assert response.status_code == 405
    event.refresh_from_db()
    assert event.get_feature_flag('show_schedule') == before


@pytest.mark.django_db
def test_get_does_not_remove_speaker(orga_client, submission):
    assert submission.speakers.count() == 1

    response = orga_client.get(
        submission.orga_urls.delete_speaker
        + '?id='
        + str(submission.speakers.first().pk)
    )

    assert response.status_code == 200
    submission.refresh_from_db()
    assert submission.speakers.count() == 1


@pytest.mark.django_db
def test_get_does_not_activate_review_phase(orga_client, event):
    with scope(event=event):
        phase = event.active_review_phase
        other_phase = event.review_phases.exclude(pk=phase.pk).first()

    response = orga_client.get(other_phase.urls.activate)

    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    with scope(event=event):
        assert event.active_review_phase == phase


@pytest.mark.django_db
def test_get_does_not_change_default_submission_type(
    orga_client, submission_type, default_submission_type
):
    response = orga_client.get(submission_type.urls.default)

    assert response.status_code == 405
    with scope(event=submission_type.event):
        submission_type.event.cfp.refresh_from_db()
        assert submission_type.event.cfp.default_type == default_submission_type


@pytest.mark.django_db
def test_get_does_not_toggle_question(orga_client, question):
    assert question.active

    response = orga_client.get(question.urls.toggle)

    assert response.status_code == 405
    with scope(event=question.event):
        assert Question.all_objects.get(pk=question.pk).active


@pytest.mark.django_db
def test_get_does_not_drop_superuser(orga_client, orga_user):
    orga_user.is_superuser = True
    orga_user.save()

    response = orga_client.get(reverse('orga:user.subuser'))

    assert response.status_code == 405
    orga_user.refresh_from_db()
    assert orga_user.is_superuser


@pytest.mark.django_db
def test_get_does_not_send_queued_mail(orga_client, event, mail):
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 1

    response = orga_client.get(mail.urls.send)

    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 1


@pytest.mark.django_db
def test_reviewer_cannot_send_queued_mail(review_client, event, mail):
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 1

    response = review_client.post(mail.urls.send, follow=True)

    assert response.status_code == 404
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 1
