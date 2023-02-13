import pytest

from pretalx.common.mail import TolerantDict
from pretalx.mail.models import QueuedMail


@pytest.mark.parametrize(
    "key,value",
    (
        ("1", "a"),
        ("2", "b"),
        ("3", "3"),
    ),
)
def test_tolerant_dict(key, value):
    d = TolerantDict({"1": "a", "2": "b"})
    assert d[key] == value


@pytest.mark.django_db
def test_sent_mail_sending(sent_mail):
    assert str(sent_mail)
    with pytest.raises(Exception):  # noqa
        sent_mail.send()


@pytest.mark.django_db
def test_mail_template_model(mail_template):
    assert mail_template.event.slug in str(mail_template)


@pytest.mark.parametrize("commit", (True, False))
@pytest.mark.django_db
def test_mail_template_model_to_mail(mail_template, commit):
    mail_template.to_mail("testdummy@exacmple.com", None, commit=commit)


@pytest.mark.django_db
def test_mail_template_model_to_mail_fails_without_address(mail_template):
    with pytest.raises(TypeError):
        mail_template.to_mail(1, None)


@pytest.mark.django_db
def test_mail_template_model_to_mail_shortens_subject(mail_template):
    mail_template.subject = "A" * 300
    mail = mail_template.to_mail("testdummy@exacmple.com", None, commit=False)
    assert len(mail.subject) == 199


@pytest.mark.django_db
@pytest.mark.parametrize(
    "text,signature,expected",
    (
        ("test", None, "test"),
        ("test", "sig", "test\n-- \nsig"),
        ("test", "-- \nsig", "test\n-- \nsig"),
    ),
)
def test_mail_make_text(event, text, signature, expected):
    if signature:
        event.mail_settings["signature"] = signature
        event.save()
    assert QueuedMail(text=text, event=event).make_text() == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "text,prefix,expected",
    (
        ("test", None, "test"),
        ("test", "pref", "[pref] test"),
        ("test", "[pref]", "[pref] test"),
    ),
)
def test_mail_make_subject(event, text, prefix, expected):
    if prefix:
        event.mail_settings["subject_prefix"] = prefix
        event.save()
    assert QueuedMail(text=text, subject=text, event=event).make_subject() == expected
