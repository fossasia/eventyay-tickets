import pytest
from django.core import mail as djmail

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
    djmail.outbox = []
    response = orga_client.post(
        mail.urls.base,
        follow=True,
        data={
            'to': 'testWIN@gmail.com',
            'bcc': mail.bcc,
            'cc': mail.cc,
            'reply_to': mail.reply_to,
            'subject': mail.subject,
            'text': mail.text,
        }
    )
    assert response.status_code == 200
    assert mail.subject in response.content.decode()
    mail.refresh_from_db()
    assert mail.to == 'testWIN@gmail.com'
    assert len(djmail.outbox) == 0


@pytest.mark.django_db
def test_orga_can_edit_and_send_pending_mail(orga_client, event, mail):
    djmail.outbox = []
    response = orga_client.post(
        mail.urls.base,
        follow=True,
        data={
            'to': 'testWIN@gmail.com',
            'bcc': mail.bcc,
            'cc': mail.cc,
            'reply_to': mail.reply_to,
            'subject': mail.subject,
            'text': 'This is the best test.',
            'form': 'send',
        }
    )
    assert response.status_code == 200
    assert mail.subject not in response.content.decode()  # Is now in the sent mail view, not in the outbox
    mail.refresh_from_db()
    assert mail.to == 'testWIN@gmail.com'
    assert len(djmail.outbox) == 1
    assert 'This is the best test.' == djmail.outbox[0].body


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
            'to': 'testfailure@gmail.com',
            'bcc': sent_mail.bcc,
            'cc': sent_mail.cc,
            'reply_to': sent_mail.reply_to,
            'subject': sent_mail.subject,
            'text': sent_mail.text,
        }
    )
    assert response.status_code == 200
    assert sent_mail.subject not in response.content.decode()
    sent_mail.refresh_from_db()
    assert sent_mail.to != 'testfailure@gmail.com'


@pytest.mark.django_db
def test_orga_can_send_all_mails(orga_client, event, mail, other_mail, sent_mail):
    assert QueuedMail.objects.filter(sent__isnull=True).count() == 2
    response = orga_client.get(event.orga_urls.send_outbox, follow=True)
    assert response.status_code == 200
    assert QueuedMail.objects.filter(sent__isnull=True).count() == 2
    response = orga_client.post(event.orga_urls.send_outbox, follow=True)
    assert response.status_code == 200
    assert QueuedMail.objects.filter(sent__isnull=True).count() == 0


@pytest.mark.django_db
def test_orga_can_send_single_mail(orga_client, event, mail, other_mail):
    assert QueuedMail.objects.filter(sent__isnull=True).count() == 2
    response = orga_client.get(mail.urls.send, follow=True)
    assert response.status_code == 200
    assert QueuedMail.objects.filter(sent__isnull=True).count() == 1


@pytest.mark.django_db
def test_orga_can_discard_all_mails(orga_client, event, mail, other_mail, sent_mail):
    assert QueuedMail.objects.filter(sent__isnull=True).count() == 2
    assert QueuedMail.objects.count() == 3
    response = orga_client.get(event.orga_urls.purge_outbox, follow=True)
    assert response.status_code == 200
    assert QueuedMail.objects.filter(sent__isnull=True).count() == 2
    assert QueuedMail.objects.count() == 3
    response = orga_client.post(event.orga_urls.purge_outbox, follow=True)
    assert response.status_code == 200
    assert QueuedMail.objects.filter(sent__isnull=True).count() == 0
    assert QueuedMail.objects.count() == 1


@pytest.mark.django_db
def test_orga_can_discard_single_mail(orga_client, event, mail, other_mail):
    assert QueuedMail.objects.count() == 2
    response = orga_client.get(mail.urls.delete, follow=True)
    assert response.status_code == 200
    assert QueuedMail.objects.count() == 1


@pytest.mark.django_db
def test_orga_cannot_send_sent_mail(orga_client, event, sent_mail):
    assert QueuedMail.objects.filter(sent__isnull=False).count() == 1
    response = orga_client.get(sent_mail.urls.send, follow=True)
    before = sent_mail.sent
    sent_mail.refresh_from_db()
    assert sent_mail.sent == before
    assert response.status_code == 200
    assert QueuedMail.objects.filter(sent__isnull=False).count() == 1


@pytest.mark.django_db
def test_orga_cannot_discard_sent_mail(orga_client, event, sent_mail):
    assert QueuedMail.objects.count() == 1
    response = orga_client.get(sent_mail.urls.delete, follow=True)
    assert response.status_code == 200
    assert QueuedMail.objects.count() == 1


@pytest.mark.django_db
def test_orga_can_copy_sent_mail(orga_client, event, sent_mail):
    assert QueuedMail.objects.count() == 1
    response = orga_client.get(sent_mail.urls.copy, follow=True)
    assert response.status_code == 200
    assert QueuedMail.objects.count() == 2


@pytest.mark.django_db
def test_orga_can_view_templates(orga_client, event, mail_template):
    response = orga_client.get(event.orga_urls.mail_templates, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_can_create_template(orga_client, event, mail_template):
    assert MailTemplate.objects.count() == 6
    response = orga_client.post(event.orga_urls.new_template, follow=True,
                                data={'subject_0': '[test] subject', 'text_0': 'text'})
    assert response.status_code == 200
    assert MailTemplate.objects.count() == 7
    assert MailTemplate.objects.get(event=event, subject__contains='[test] subject')


@pytest.mark.django_db
@pytest.mark.parametrize('variant', ('custom', 'fixed'))
def test_orga_can_edit_template(orga_client, event, mail_template, variant):
    if variant == 'fixed':
        mail_template = event.ack_template
    assert MailTemplate.objects.count() == 6
    response = orga_client.get(mail_template.urls.edit, follow=True)
    assert response.status_code == 200
    response = orga_client.post(mail_template.urls.edit, follow=True,
                                data={'subject_0': 'COMPLETELY NEW AND UNHEARD OF', 'text_0': mail_template.text})
    assert response.status_code == 200
    assert MailTemplate.objects.count() == 6
    assert MailTemplate.objects.get(event=event, subject__contains='COMPLETELY NEW AND UNHEARD OF')


@pytest.mark.django_db
def test_orga_cannot_add_wrong_placeholder_in_template(orga_client, event):
    assert MailTemplate.objects.count() == 5
    mail_template = event.ack_template
    response = orga_client.post(mail_template.urls.edit, follow=True,
                                data={'subject_0': 'COMPLETELY NEW AND UNHEARD OF', 'text_0': str(mail_template.text) + '{wrong_placeholder}'})
    assert response.status_code == 200
    mail_template.refresh_from_db()
    assert 'COMPLETELY' not in str(mail_template.subject)
    assert '{wrong_placeholder}' not in str(mail_template.text)


@pytest.mark.django_db
def test_orga_can_delete_template(orga_client, event, mail_template):
    assert MailTemplate.objects.count() == 6
    response = orga_client.post(mail_template.urls.delete, follow=True)
    assert response.status_code == 200
    assert MailTemplate.objects.count() == 5


@pytest.mark.django_db
def test_orga_can_compose_single_mail(orga_client, event, submission):
    assert QueuedMail.objects.filter(sent__isnull=True).count() == 0
    response = orga_client.post(
        event.orga_urls.send_mails, follow=True,
        data={'recipients': 'submitted', 'bcc': '', 'cc': '', 'reply_to': '', 'subject': 'foo', 'text': 'bar'}
    )
    assert response.status_code == 200
    assert QueuedMail.objects.filter(sent__isnull=True).count() == 1
