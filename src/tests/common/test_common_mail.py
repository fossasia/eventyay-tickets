import pytest

from pretalx.common.mail import mail_send_task


@pytest.mark.django_db
def test_mail_send_does_not_fail_in_corner_cases(event):
    event.settings.mail_reply_to = "sender@example.com"
    mail_send_task("m@example.com", "S", "B", None, [], event.pk)


@pytest.mark.django_db
def test_mail_send_does_not_fail_with_sender(event):
    event.settings.mail_reply_to = "sender@example.com"
    event.settings.mail_from = "sender@example.com"
    mail_send_task("m@example.com", "S", "B", None, [], event.pk)
