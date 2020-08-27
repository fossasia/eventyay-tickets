import json

import pytest
from django.urls import reverse


@pytest.mark.parametrize(
    "search,results,orga_results",
    (
        ("a", 0, 0),
        ("aa", 0, 0),
        ("aaa", 0, 0),
        ("Jane S", 1, 0),
    ),
)
@pytest.mark.django_db
def test_user_typeahead(
    orga_client, event, speaker, other_orga_user, search, results, orga_results
):
    response = orga_client.get(
        reverse("orga:event.user_list", kwargs={"event": event.slug}),
        data={"search": search},
        follow=True,
    )
    orga_response = orga_client.get(
        reverse("orga:event.user_list", kwargs={"event": event.slug}),
        data={"search": search, "orga": True},
        follow=True,
    )
    assert response.status_code == 200
    assert orga_response.status_code == 200
    content = json.loads(response.content.decode())
    orga_content = json.loads(orga_response.content.decode())
    assert content["count"] == results
    assert orga_content["count"] == orga_results

    if results:
        assert "name" in content["results"][0]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "follow,expected", (("/orga/", "/orga/"), ("https://example.com", "/orga/event/"))
)
def test_remove_superuser(orga_client, orga_user, follow, expected):
    orga_user.is_superuser = True
    orga_user.save()
    response = orga_client.get(
        reverse("orga:user.subuser"),
        data={"next": follow},
    )

    orga_user.refresh_from_db()
    assert response.status_code == 302
    assert response.url == expected
    assert not orga_user.is_superuser


@pytest.mark.django_db
def test_remove_superuser_if_no_superuser(orga_client, orga_user):
    response = orga_client.get(reverse("orga:user.subuser"), follow=True)

    orga_user.refresh_from_db()
    assert response.status_code == 200
    assert not orga_user.is_superuser


@pytest.mark.django_db
def test_orga_reset_auth_token(orga_client, orga_user):
    assert not getattr(orga_user, "auth_token", None)
    response = orga_client.get(reverse("orga:user.view"), follow=True)
    assert response.status_code == 200
    orga_user.refresh_from_db()
    assert orga_user.auth_token
    old_token = orga_user.auth_token.key
    response = orga_client.post(
        reverse("orga:user.view"), {"form": "token"}, follow=True
    )
    assert response.status_code == 200
    orga_user.refresh_from_db()
    assert orga_user.auth_token
    assert orga_user.auth_token.key != old_token


@pytest.mark.django_db
def test_orga_wrong_profile_page_update(orga_client, orga_user):
    response = orga_client.post(
        reverse("orga:user.view"), {"form": "tokennnnnn"}, follow=True
    )
    assert response.status_code == 200
    assert "trouble saving your input" in response.content.decode()


@pytest.mark.django_db
def test_orga_update_login_info(orga_client, orga_user):
    response = orga_client.post(
        reverse("orga:user.view"),
        {
            "form": "login",
            "old_password": "orgapassw0rd",
            "password": "tr4lalalala",
            "password_repeat": "tr4lalalala",
            "email": orga_user.email,
        },
        follow=True,
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_orga_update_profile_info(orga_client, orga_user):
    response = orga_client.post(
        reverse("orga:user.view"),
        {"form": "profile", "name": "New name", "locale": "en"},
        follow=True,
    )
    assert response.status_code == 200
    assert "have been saved" in response.content.decode()
    orga_user.refresh_from_db()
    assert orga_user.name == "New name"
