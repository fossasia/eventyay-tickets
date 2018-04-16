import pytest

from pretalx.common.mail import TolerantDict


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
    assert sent_mail.event.slug in str(sent_mail)
    with pytest.raises(Exception):
        sent_mail.send()
