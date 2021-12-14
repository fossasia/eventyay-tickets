import pytest

from pretalx.common.mail import mail_send_task


@pytest.mark.django_db
def test_mail_send_does_not_fail_in_corner_cases(event):
    event.mail_settings["reply_to"] = "sender@example.com"
    event.save()
    mail_send_task("m@example.com", "S", "B", None, [], event.pk)


@pytest.mark.django_db
def test_mail_send_does_not_fail_with_sender(event):
    event.mail_settings["reply_to"] = "sender@example.com"
    event.mail_settings["mail_from"] = "sender@example.com"
    event.save()
    mail_send_task("m@example.com", "S", "B", None, [], event.pk)
