import json

import pytest
import responses

from pretalx.common.models.settings import GlobalSettings
from pretalx.person.models import User


@pytest.mark.django_db
@pytest.mark.parametrize("is_administrator", (True, False))
def test_admin_dashboard_only_for_admin_user(orga_user, orga_client, is_administrator):
    orga_user.is_administrator = is_administrator
    orga_user.save()
    response = orga_client.get("/orga/admin/")
    assert (response.status_code == 200) is is_administrator
    assert (
        "Administrator information" in response.content.decode()
    ) is is_administrator


@pytest.fixture
def user():
    user = User.objects.create_user(email="dummy@dummy.dummy", password="dummy")
    return user


def request_callback_updatable(request):
    json_data = json.loads(request.body.decode())
    resp_body = {
        "status": "ok",
        "version": {
            "latest": "1000.0.0",
            "yours": json_data.get("version"),
            "updatable": True,
        },
        "plugins": {},
    }
    return 200, {"Content-Type": "text/json"}, json.dumps(resp_body)


@pytest.mark.django_db
def test_update_notice_displayed(client, user):
    client.login(email="dummy@dummy.dummy", password="dummy")

    r = client.get("/orga/", follow=True)
    assert (
        "pretalx automatically checks for updates in the background"
        not in r.content.decode()
    )

    user.is_administrator = True
    user.save()
    r = client.get("/orga/", follow=True)
    assert (
        "pretalx automatically checks for updates in the background"
        in r.content.decode()
    )

    client.get("/orga/admin/update/")  # Click it
    r = client.get("/orga/", follow=True)
    assert (
        "pretalx automatically checks for updates in the background"
        not in r.content.decode()
    )


@pytest.mark.django_db
def test_settings(client, user):
    user.is_administrator = True
    user.save()
    client.login(email="dummy@dummy.dummy", password="dummy")

    client.post(
        "/orga/admin/update/",
        {"update_check_email": "test@example.com", "update_check_enabled": "on"},
    )
    gs = GlobalSettings()
    gs.settings.flush()
    assert gs.settings.update_check_enabled
    assert gs.settings.update_check_email

    client.post(
        "/orga/admin/update/", {"update_check_email": "", "update_check_enabled": ""}
    )
    gs.settings.flush()
    assert not gs.settings.update_check_enabled
    assert not gs.settings.update_check_email


@pytest.mark.django_db
@responses.activate
def test_trigger(client, user):
    responses.add_callback(
        responses.POST,
        "https://pretalx.com/.update_check/",
        callback=request_callback_updatable,
        content_type="application/json",
    )

    user.is_administrator = True
    user.save()
    client.login(email="dummy@dummy.dummy", password="dummy")

    gs = GlobalSettings()
    assert not gs.settings.update_check_last
    client.post("/orga/admin/update/", {"trigger": "on"})
    gs.settings.flush()
    assert gs.settings.update_check_last
