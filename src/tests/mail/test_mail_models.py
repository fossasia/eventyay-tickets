import pytest

from pretalx.common.mail import TolerantDict
from pretalx.mail.models import QueuedMail


@pytest.mark.parametrize('key,value', (
    ('1', 'a'),
    ('2', 'b'),
    ('3', '3'),
))
def test_tolerant_dict(key, value):
    d = TolerantDict({'1': 'a', '2': 'b'})
    assert d[key] == value


@pytest.mark.django_db
def test_sent_mail_sending(mail_template, sent_mail):
    assert mail_template.event.slug in str(mail_template)
    assert str(sent_mail)
    with pytest.raises(Exception):
        sent_mail.send()


@pytest.mark.django_db
@pytest.mark.parametrize('text,signature,expected', (
    ('test', None, 'test'),
    ('test', 'sig', 'test\n-- \nsig'),
    ('test', '-- \nsig', 'test\n-- \nsig'),
))
def test_mail_make_text(event, text, signature, expected):
    if signature:
        event.settings.mail_signature = signature
    assert QueuedMail.make_text(text, event) == expected


@pytest.mark.django_db
@pytest.mark.parametrize('text,prefix,expected', (
    ('test', None, 'test'),
    ('test', 'pref', '[pref] test'),
    ('test', '[pref]', '[pref] test'),
))
def test_mail_make_subject(event, text, prefix, expected):
    if prefix:
        event.settings.mail_subject_prefix = prefix
    assert QueuedMail.make_subject(text, event) == expected
