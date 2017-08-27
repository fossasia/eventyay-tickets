import pytest

from pretalx.mail.models import MailTemplate


@pytest.mark.django_db
def test_orga_can_view_templates(orga_client, event, mail_template):
    response = orga_client.get(event.orga_urls.mail_templates, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_can_create_template(orga_client, event, mail_template):
    assert MailTemplate.objects.count() == 5
    response = orga_client.post(event.orga_urls.new_template, follow=True,
                                data={'subject_0': '[test] subject', 'text_0': 'text'})
    assert response.status_code == 200
    assert MailTemplate.objects.count() == 6
    assert MailTemplate.objects.get(event=event, subject__contains='[test] subject')


@pytest.mark.django_db
def test_orga_can_edit_template(orga_client, event, mail_template):
    assert MailTemplate.objects.count() == 5
    response = orga_client.post(mail_template.urls.edit, follow=True,
                                data={'subject_0': 'COMPLETELY NEW AND UNHEARD OF', 'text_0': mail_template.text})
    assert response.status_code == 200
    assert MailTemplate.objects.count() == 5
    assert MailTemplate.objects.get(event=event, subject__contains='COMPLETELY NEW AND UNHEARD OF')


@pytest.mark.django_db
def test_orga_can_delete_template(orga_client, event, mail_template):
    assert MailTemplate.objects.count() == 5
    response = orga_client.post(mail_template.urls.delete, follow=True)
    assert response.status_code == 200
    assert MailTemplate.objects.count() == 4
