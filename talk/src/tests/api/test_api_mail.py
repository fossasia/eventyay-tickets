import json

import pytest
from django_scopes import scope

from pretalx.api.serializers.mail import MailTemplateSerializer


@pytest.mark.django_db
def test_mail_template_serializer(mail_template):
    with scope(event=mail_template.event):
        data = MailTemplateSerializer(
            mail_template, context={"event": mail_template.event}
        ).data
        assert set(data.keys()) == {
            "id",
            "role",
            "subject",
            "text",
            "reply_to",
            "bcc",
        }


@pytest.mark.parametrize("is_public", (True, False))
@pytest.mark.django_db
def test_cannot_see_mail_templates(client, mail_template, is_public):
    with scope(event=mail_template.event):
        mail_template.event.is_public = is_public
        mail_template.event.save()
    response = client.get(mail_template.event.api_urls.mail_templates, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_see_mail_templates(client, orga_user_token, mail_template):
    response = client.get(
        mail_template.event.api_urls.mail_templates,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] > 0
    assert mail_template.subject in [
        template["subject"]["en"] for template in content["results"]
    ]


@pytest.mark.django_db
def test_orga_can_see_single_mail_template(client, orga_user_token, mail_template):
    response = client.get(
        mail_template.event.api_urls.mail_templates + f"{mail_template.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["subject"]["en"] == mail_template.subject
    assert isinstance(content["subject"], dict)


@pytest.mark.django_db
def test_orga_can_see_single_mail_template_locale_override(
    client, orga_user_token, mail_template
):
    response = client.get(
        mail_template.event.api_urls.mail_templates + f"{mail_template.pk}/?lang=en",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert isinstance(content["subject"], str)


@pytest.mark.django_db
def test_no_legacy_mail_template_api(client, orga_user_token, mail_template):
    from pretalx.api.versions import LEGACY

    response = client.get(
        mail_template.event.api_urls.mail_templates + f"{mail_template.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Pretalx-Version": LEGACY,
        },
    )
    assert response.status_code == 400, response.text
    assert "API version not supported." in response.text


@pytest.mark.django_db
def test_orga_can_create_mail_templates(client, orga_user_write_token, event):
    response = client.post(
        event.api_urls.mail_templates,
        follow=True,
        data={
            "subject": "newtesttemplate",
            "text": "test body",
            "role": "submission.state.accepted",
            "foo": "bar",
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201, response.text
    with scope(event=event):
        mail_template = event.mail_templates.get(subject="newtesttemplate")
        assert not mail_template.role
        assert (
            mail_template.logged_actions()
            .filter(action_type="pretalx.mail_template.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_create_mail_templates_readonly_token(
    client, orga_user_token, event
):
    response = client.post(
        event.api_urls.mail_templates,
        follow=True,
        data={"subject": "newtesttemplate", "text": "test body"},
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=event):
        assert not event.mail_templates.filter(subject="newtesttemplate").exists()
        assert (
            not event.logged_actions()
            .filter(action_type="pretalx.mail_template.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_update_mail_templates(
    client, orga_user_write_token, event, mail_template
):
    assert mail_template.subject != "newtesttemplate"
    response = client.patch(
        event.api_urls.mail_templates + f"{mail_template.pk}/",
        follow=True,
        data=json.dumps({"subject": "newtesttemplate"}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    with scope(event=mail_template.event):
        mail_template.refresh_from_db()
        assert mail_template.subject == "newtesttemplate"
        assert (
            mail_template.logged_actions()
            .filter(action_type="pretalx.mail_template.update")
            .exists()
        )


@pytest.mark.parametrize("field", ("text", "subject"))
@pytest.mark.parametrize(
    "value", ("test {invalidplaceholder}", "{invalid placeholder}")
)
@pytest.mark.django_db
def test_orga_update_mail_template_invalid_placeholder(
    client, orga_user_write_token, event, mail_template, field, value
):
    assert mail_template.subject != "newtesttemplate"
    response = client.patch(
        event.api_urls.mail_templates + f"{mail_template.pk}/",
        follow=True,
        data=json.dumps({field: value}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 400
    with scope(event=mail_template.event):
        mail_template.refresh_from_db()
        assert getattr(mail_template, field) != value
        assert not (
            mail_template.logged_actions()
            .filter(action_type="pretalx.mail_template.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_update_mail_template_roles(client, orga_user_write_token, event):
    with scope(event=event):
        mail_template = event.mail_templates.get(role="submission.state.accepted")
    response = client.patch(
        event.api_urls.mail_templates + f"{mail_template.pk}/",
        follow=True,
        data=json.dumps({"role": "submission.state.rejected"}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    with scope(event=mail_template.event):
        mail_template.refresh_from_db()
        assert mail_template.role == "submission.state.accepted"


@pytest.mark.django_db
def test_orga_cannot_update_mail_templates_readonly_token(
    client, orga_user_token, mail_template
):
    response = client.patch(
        mail_template.event.api_urls.mail_templates + f"{mail_template.pk}/",
        follow=True,
        data=json.dumps({"subject": "newtesttemplate"}),
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403
    with scope(event=mail_template.event):
        mail_template.refresh_from_db()
        assert mail_template.subject != "newtesttemplate"
        assert (
            not mail_template.logged_actions()
            .filter(action_type="pretalx.mail_template.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_delete_mail_templates(
    client, orga_user_write_token, event, mail_template
):
    response = client.delete(
        event.api_urls.mail_templates + f"{mail_template.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 204
    with scope(event=event):
        assert not event.mail_templates.filter(pk=mail_template.pk).exists()
        assert (
            event.logged_actions()
            .filter(action_type="pretalx.mail_template.delete")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_delete_mail_templates_readonly_token(
    client, orga_user_token, event, mail_template
):
    response = client.delete(
        event.api_urls.mail_templates + f"{mail_template.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403
    with scope(event=event):
        assert event.mail_templates.filter(pk=mail_template.pk).exists()
