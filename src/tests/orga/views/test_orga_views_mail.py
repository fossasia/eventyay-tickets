import pytest
from django.core import mail as djmail
from django_scopes import scope

from pretalx.mail.models import MailTemplate, QueuedMail


@pytest.mark.django_db
def test_orga_can_view_pending_mails(orga_client, event, mail, other_mail):
    response = orga_client.get(event.orga_urls.outbox)
    assert response.status_code == 200
    assert mail.subject in response.content.decode()


@pytest.mark.django_db
def test_orga_can_view_sent_mails(orga_client, event, sent_mail):
    response = orga_client.get(event.orga_urls.sent_mails)
    assert response.status_code == 200
    assert sent_mail.subject in response.content.decode()


@pytest.mark.django_db
def test_orga_can_view_pending_mail(orga_client, event, mail):
    response = orga_client.get(mail.urls.base)
    assert response.status_code == 200
    assert mail.subject in response.content.decode()


@pytest.mark.django_db
def test_orga_can_edit_pending_mail(orga_client, event, mail):
    with scope(event=event):
        count = mail.logged_actions().count()
    djmail.outbox = []
    response = orga_client.post(
        mail.urls.base,
        follow=True,
        data={
            "to": "testWIN@gmail.com",
            "bcc": mail.bcc or "",
            "cc": mail.cc or "",
            "reply_to": mail.reply_to or "",
            "subject": mail.subject,
            "text": mail.text or "",
        },
    )
    assert response.status_code == 200
    assert mail.subject in response.content.decode()
    mail.refresh_from_db()
    assert mail.to == "testwin@gmail.com"
    assert len(djmail.outbox) == 0
    with scope(event=event):
        assert mail.logged_actions().count() == count + 1


@pytest.mark.django_db
def test_orga_can_edit_pending_mail_unchanged(orga_client, event, mail):
    with scope(event=event):
        count = mail.logged_actions().count()
    djmail.outbox = []
    response = orga_client.post(
        mail.urls.base,
        follow=True,
        data={
            "to": mail.to or "",
            "bcc": mail.bcc or "",
            "cc": mail.cc or "",
            "reply_to": mail.reply_to or "",
            "subject": mail.subject,
            "text": mail.text or "",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert mail.logged_actions().count() == count


@pytest.mark.django_db
def test_orga_can_edit_and_send_pending_mail(orga_client, event, mail):
    djmail.outbox = []
    response = orga_client.post(
        mail.urls.base,
        follow=True,
        data={
            "to": "testWIN@gmail.com",
            "bcc": "foo@bar.com,bar@bar.com",
            "cc": "",
            "reply_to": mail.reply_to,
            "subject": mail.subject,
            "text": "This is the best test.",
            "form": "send",
        },
    )
    assert response.status_code == 200
    assert (
        mail.subject not in response.content.decode()
    )  # Is now in the sent mail view, not in the outbox
    mail.refresh_from_db()
    assert mail.to == "testwin@gmail.com"
    assert mail.cc != "None"
    assert len(djmail.outbox) == 1
    real_mail = djmail.outbox[0]
    assert real_mail.body == "This is the best test."
    assert real_mail.to == ["testwin@gmail.com"]
    assert real_mail.cc == [""]
    assert real_mail.bcc == ["foo@bar.com", "bar@bar.com"]


@pytest.mark.django_db
def test_orga_can_view_sent_mail(orga_client, event, sent_mail):
    response = orga_client.get(sent_mail.urls.base)
    assert response.status_code == 200
    assert sent_mail.subject in response.content.decode()


@pytest.mark.django_db
def test_orga_cannot_edit_sent_mail(orga_client, event, sent_mail):
    response = orga_client.post(
        sent_mail.urls.base,
        follow=True,
        data={
            "to": "testfailure@gmail.com",
            "bcc": sent_mail.bcc or "",
            "cc": sent_mail.cc or "",
            "reply_to": sent_mail.reply_to or "",
            "subject": "WILD NEW SUBJECT APPEARS",
            "text": sent_mail.text or "",
        },
    )
    assert response.status_code == 200
    assert sent_mail.subject in response.content.decode()
    sent_mail.refresh_from_db()
    assert sent_mail.to != "testfailure@gmail.com"


@pytest.mark.django_db
def test_orga_can_send_all_mails(orga_client, event, mail, other_mail, sent_mail):
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 2
    response = orga_client.get(event.orga_urls.send_outbox, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 2
    response = orga_client.post(event.orga_urls.send_outbox, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 0


@pytest.mark.django_db
def test_orga_can_send_single_mail(orga_client, event, mail, other_mail):
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 2
    response = orga_client.get(mail.urls.send, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 1


@pytest.mark.django_db
def test_orga_cannot_send_single_wrong_mail(orga_client, event, mail, other_mail):
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 2
    response = orga_client.get(
        mail.urls.send.replace(str(mail.pk), str(mail.pk + 100)), follow=True
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 2


@pytest.mark.django_db
def test_orga_can_discard_all_mails(orga_client, event, mail, other_mail, sent_mail):
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 2
        assert QueuedMail.objects.count() == 3
    response = orga_client.get(event.orga_urls.purge_outbox, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 2
        assert QueuedMail.objects.count() == 3
    response = orga_client.post(event.orga_urls.purge_outbox, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 0
        assert QueuedMail.objects.count() == 1


@pytest.mark.django_db
def test_orga_can_discard_all_mails_by_template(
    orga_client, event, mail, other_mail, sent_mail, mail_template
):
    with scope(event=event):
        QueuedMail.objects.all().update(template=mail_template)
        assert QueuedMail.objects.count() == 3
    response = orga_client.post(mail.urls.delete + "?all=true", follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 0
        assert QueuedMail.objects.count() == 1


@pytest.mark.django_db
def test_orga_can_view_discard_mail_confirm(orga_client, event, mail):
    with scope(event=event):
        assert QueuedMail.objects.count() == 1
    response = orga_client.get(mail.urls.delete, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_can_discard_single_mail(orga_client, event, mail, other_mail):
    with scope(event=event):
        assert QueuedMail.objects.count() == 2
    response = orga_client.post(mail.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.count() == 1


@pytest.mark.django_db
def test_orga_cannot_send_sent_mail(orga_client, event, sent_mail):
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=False).count() == 1
    response = orga_client.get(sent_mail.urls.send, follow=True)
    before = sent_mail.sent
    sent_mail.refresh_from_db()
    assert sent_mail.sent == before
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=False).count() == 1


@pytest.mark.django_db
def test_orga_cannot_discard_sent_mail(orga_client, event, sent_mail):
    with scope(event=event):
        assert QueuedMail.objects.count() == 1
    response = orga_client.get(sent_mail.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.count() == 1


@pytest.mark.django_db
def test_orga_can_copy_sent_mail(orga_client, event, sent_mail):
    with scope(event=event):
        assert QueuedMail.objects.count() == 1
    response = orga_client.get(sent_mail.urls.copy, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.count() == 2


@pytest.mark.django_db
def test_orga_can_view_templates(orga_client, event, mail_template):
    response = orga_client.get(event.orga_urls.mail_templates, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_can_create_template(orga_client, event, mail_template):
    with scope(event=event):
        assert MailTemplate.objects.count() == 6
    response = orga_client.post(
        event.orga_urls.new_template,
        follow=True,
        data={"subject_0": "[test] subject", "text_0": "text"},
    )
    assert response.status_code == 200
    with scope(event=event):
        assert MailTemplate.objects.count() == 7
        assert MailTemplate.objects.get(event=event, subject__contains="[test] subject")


@pytest.mark.django_db
@pytest.mark.parametrize("variant", ("custom", "fixed", "update"))
def test_orga_can_edit_template(orga_client, event, mail_template, variant):
    if variant == "fixed":
        mail_template = event.ack_template
    elif variant == "update":
        mail_template = event.update_template
    with scope(event=event):
        assert MailTemplate.objects.count() == 6
        count = mail_template.logged_actions().count()
    response = orga_client.get(mail_template.urls.edit, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        mail_template.urls.edit,
        follow=True,
        data={
            "subject_0": "COMPLETELY NEW AND UNHEARD OF",
            "text_0": mail_template.text,
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert MailTemplate.objects.count() == 6
        assert count + 1 == mail_template.logged_actions().count()
        assert MailTemplate.objects.get(
            event=event, subject__contains="COMPLETELY NEW AND UNHEARD OF"
        )


@pytest.mark.django_db
def test_orga_can_edit_template_without_change(orga_client, event, mail_template):
    with scope(event=event):
        count = mail_template.logged_actions().count()
    response = orga_client.get(mail_template.urls.edit, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        mail_template.urls.edit,
        follow=True,
        data={
            "subject_0": str(mail_template.subject),
            "text_0": mail_template.text,
            "reply_to": mail_template.reply_to,
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert count == mail_template.logged_actions().count()


@pytest.mark.django_db
def test_orga_cannot_add_wrong_placeholder_in_template(orga_client, event):
    with scope(event=event):
        assert MailTemplate.objects.count() == 5
    mail_template = event.ack_template
    response = orga_client.post(
        mail_template.urls.edit,
        follow=True,
        data={
            "subject_0": "COMPLETELY NEW AND UNHEARD OF",
            "text_0": str(mail_template.text) + "{wrong_placeholder}",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        mail_template.refresh_from_db()
    assert "COMPLETELY" not in str(mail_template.subject)
    assert "{wrong_placeholder}" not in str(mail_template.text)


@pytest.mark.django_db
def test_orga_can_delete_template(orga_client, event, mail_template):
    with scope(event=event):
        assert MailTemplate.objects.count() == 6
    response = orga_client.post(mail_template.urls.delete, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert MailTemplate.objects.count() == 5


@pytest.mark.django_db
def test_orga_can_compose_single_mail_team(orga_client, review_user, event):
    response = orga_client.get(
        event.orga_urls.compose_mails_teams,
        follow=True,
    )
    assert response.status_code == 200
    djmail.outbox = []
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=False).count() == 0
    response = orga_client.post(
        event.orga_urls.compose_mails_teams,
        follow=True,
        data={
            "recipients": f"{review_user.teams.first().pk}",
            "subject_0": "foo {name}",
            "text_0": "bar {name}",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=False).count() == 0
        assert len(djmail.outbox) == 1
        mail = djmail.outbox[0]
        assert mail.subject == f"foo {review_user.name}"
        assert mail.body == f"bar {review_user.name}"


@pytest.mark.django_db
def test_orga_can_compose_single_mail_team_by_pk(
    orga_user, orga_client, review_user, event
):
    team = orga_user.teams.first()
    assert team in event.teams.all()
    djmail.outbox = []
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=False).count() == 0
    response = orga_client.post(
        event.orga_urls.compose_mails_teams,
        follow=True,
        data={
            "recipients": [f"{review_user.teams.first().pk}", str(team.pk)],
            "subject_0": "foo {name}",
            "text_0": "bar {email}",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=False).count() == 0
        assert len(djmail.outbox) == 2
        for user in [orga_user, review_user]:
            mail = [m for m in djmail.outbox if m.subject == f"foo {user.name}"][0]
            assert mail.body == f"bar {user.email}"


@pytest.mark.django_db
def test_orga_can_compose_single_mail(
    orga_client, speaker, event, submission, other_submission
):
    response = orga_client.get(
        event.orga_urls.compose_mails_sessions,
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 0
        other_submission.accept()
    response = orga_client.post(
        event.orga_urls.compose_mails_sessions,
        follow=True,
        data={
            "state": "submitted",
            "bcc": "",
            "cc": "",
            "reply_to": "",
            "subject_0": "foo {name}",
            "text_0": "bar {submission_title}",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        mails = QueuedMail.objects.filter(sent__isnull=True)
        assert mails.count() == 2  # one of them is the accept mail!
        mail = [m for m in mails if m.subject == f"foo {speaker.name}"][0]
        assert mail.text == f"bar {submission.title}"


@pytest.mark.django_db
def test_orga_can_compose_single_mail_multiple_states_and_failing_placeholders(
    orga_client, orga_user, event, slot, other_submission
):
    with scope(event=event):
        QueuedMail.objects.filter(sent__isnull=True).delete()
    response = orga_client.post(
        event.orga_urls.compose_mails_sessions,
        follow=True,
        data={
            "recipients": ["submitted", "confirmed"],
            "bcc": "",
            "cc": "",
            "reply_to": "",
            "subject_0": "foo {name}",
            "text_0": "bar {session_room}",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert (
            QueuedMail.objects.filter(sent__isnull=True).count() == 1
        )  # only one, the other fails for lack of a room name!
        assert (
            QueuedMail.objects.filter(sent__isnull=True).first().text
            == f"bar {slot.room.name}"
        )


@pytest.mark.django_db
def test_orga_can_compose_single_mail_with_specific_submission(
    orga_client, speaker, event, slot, other_submission
):
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).delete()
    response = orga_client.post(
        event.orga_urls.compose_mails_sessions,
        follow=True,
        data={
            "state": "submitted",
            "submissions": slot.submission.code,
            "bcc": "",
            "cc": "",
            "reply_to": "",
            "subject_0": "foo {name}",
            "text_0": "bar {submission_title}",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        mails = QueuedMail.objects.filter(sent__isnull=True)
        assert mails.count() == 2
        for title in [slot.submission.title, other_submission.title]:
            mail = [m for m in mails if m.text == f"bar {title}"][0]
            assert mail


@pytest.mark.django_db
def test_orga_can_compose_single_mail_with_specific_submission_immediately(
    orga_client, speaker, event, slot, other_submission
):
    with scope(event=event):
        QueuedMail.objects.all().delete()
    djmail.outbox = []
    response = orga_client.post(
        event.orga_urls.compose_mails_sessions,
        follow=True,
        data={
            "state": "submitted",
            "submissions": slot.submission.code,
            "bcc": "",
            "cc": "",
            "reply_to": "",
            "subject_0": "foo {name}",
            "text_0": "bar {submission_title}",
            "skip_queue": "on",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 0
        assert QueuedMail.objects.filter(sent__isnull=False).count() == 2
        assert len(djmail.outbox) == 2
        for title in [slot.submission.title, other_submission.title]:
            mail = [m for m in djmail.outbox if m.body == f"bar {title}"][0]
            assert mail


@pytest.mark.django_db
def test_orga_can_compose_mail_for_track(orga_client, event, submission, track):
    with scope(event=event):
        submission.track = track
        submission.save()
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 0
    response = orga_client.post(
        event.orga_urls.compose_mails_sessions,
        follow=True,
        data={
            "bcc": "",
            "cc": "",
            "reply_to": "",
            "subject_0": "foo",
            "text_0": "bar",
            "tracks": [track.pk],
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 1


@pytest.mark.django_db
def test_orga_can_compose_mail_for_submission_type(orga_client, event, submission):
    response = orga_client.get(
        event.orga_urls.compose_mails_sessions,
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 0
    response = orga_client.post(
        event.orga_urls.compose_mails_sessions,
        follow=True,
        data={
            "bcc": "",
            "cc": "",
            "reply_to": "",
            "subject_0": "foo",
            "text_0": "bar",
            "submission_types": [submission.submission_type.pk],
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 1


@pytest.mark.django_db
def test_orga_can_compose_mail_for_track_and_type_no_doubles(
    orga_client, event, submission, track
):
    with scope(event=event):
        submission.track = track
        submission.save()
    response = orga_client.get(
        event.orga_urls.compose_mails_sessions,
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 0
    response = orga_client.post(
        event.orga_urls.compose_mails_sessions,
        follow=True,
        data={
            "bcc": "",
            "cc": "",
            "reply_to": "",
            "subject_0": "foo",
            "text_0": "bar",
            "tracks": [track.pk],
            "submission_types": [submission.submission_type.pk],
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 1


@pytest.mark.django_db
def test_orga_can_compose_single_mail_selected_submissions(
    orga_client, event, submission, other_submission
):
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 0
    response = orga_client.post(
        event.orga_urls.compose_mails_sessions,
        follow=True,
        data={
            "submissions": [other_submission.code],
            "bcc": "",
            "cc": "",
            "reply_to": "",
            "subject_0": "foo",
            "text_0": "bar",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        mails = list(QueuedMail.objects.filter(sent__isnull=True))
        assert len(mails) == 1
        assert not mails[0].to
        assert list(mails[0].to_users.all()) == [other_submission.speakers.first()]


@pytest.mark.django_db
def test_orga_can_compose_single_mail_to_additional_recipients(
    orga_client,
    event,
    submission,
    other_submission,
    orga_user,
):
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 0
    response = orga_client.post(
        event.orga_urls.compose_mails_sessions,
        follow=True,
        data={
            "additional_recipients": f"foot@example.com,{orga_user.email}",
            "bcc": "",
            "cc": "",
            "reply_to": "",
            "subject_0": "foo",
            "text_0": "bar",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        mails = list(QueuedMail.objects.filter(sent__isnull=True))
        assert len(mails) == 2


@pytest.mark.django_db
def test_orga_can_compose_mail_to_speakers_with_no_slides(
    orga_client, event, orga_user, slot, confirmed_submission
):
    with scope(event=event):
        assert QueuedMail.objects.filter(sent__isnull=True).count() == 1
    response = orga_client.post(
        event.orga_urls.compose_mails_sessions,
        follow=True,
        data={
            "recipients": "no_slides",
            "bcc": "",
            "cc": "",
            "reply_to": "",
            "subject_0": "foo",
            "text_0": "bar",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        mails = list(QueuedMail.objects.filter(sent__isnull=True))
        assert len(mails) == 2
        assert not mails[-1].to
        assert list(mails[-1].to_users.all()) == [confirmed_submission.speakers.first()]


@pytest.mark.django_db
def test_orga_can_compose_single_mail_from_template(
    orga_client, event, submission, orga_user
):
    response = orga_client.get(
        event.orga_urls.compose_mails_sessions
        + f"?template={event.ack_template.pk}&submission={submission.code}&email={orga_user.email}",
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert str(event.ack_template.subject) in response.content.decode()


@pytest.mark.django_db
def test_orga_can_compose_single_mail_from_wrong_template(
    orga_client, event, submission
):
    response = orga_client.get(
        event.orga_urls.compose_mails_sessions
        + f"?template={event.ack_template.pk}000&submission={submission.code}EEE&email=r",
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        assert str(event.ack_template.subject) not in response.content.decode()
