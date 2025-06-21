import pytest
from django.core import mail as djmail

from pretalx.common.mail import mail_send_task


@pytest.mark.django_db
def test_mail_send(event):
    djmail.outbox = []
    mail_send_task("m@example.com", "S", "B", None, [], event.pk)
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ["m@example.com"]
    assert djmail.outbox[0].from_email == f"{event.name} <orga@orga.org>"
    assert djmail.outbox[0].reply_to == [f"{event.name} <{event.email}>"]


@pytest.mark.django_db
def test_mail_send_ignored_sender_but_custom_reply_to(event):
    event.mail_settings["reply_to"] = "sender@example.com"
    event.mail_settings["mail_from"] = "sender@example.com"
    event.save()
    djmail.outbox = []
    mail_send_task("m@example.com", "S", "B", None, [], event.pk)
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ["m@example.com"]
    assert djmail.outbox[0].from_email == f"{event.name} <orga@orga.org>"
    assert djmail.outbox[0].reply_to == [f"{event.name} <sender@example.com>"]


@pytest.mark.django_db
def test_mail_send_exits_early_without_address(event):
    djmail.outbox = []
    mail_send_task("", "S", "B", None, [], event.pk)
    assert djmail.outbox == []
