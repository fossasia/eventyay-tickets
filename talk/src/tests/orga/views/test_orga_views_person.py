import json

import pytest
from django.urls import reverse


@pytest.mark.parametrize(
    "search,orga_results",
    (
        ("a", 0),
        ("aa", 0),
        ("aaa", 0),
        ("Jane S", 1),
    ),
)
@pytest.mark.django_db
def test_user_typeahead(
    orga_client,
    event,
    speaker,
    submission,
    other_orga_user,
    search,
    orga_results,
):
    orga_response = orga_client.get(
        reverse("orga:organiser.user_list", kwargs={"organiser": event.organiser.slug}),
        data={"search": search, "orga": True},
        follow=True,
    )
    assert orga_response.status_code == 200
    orga_content = json.loads(orga_response.text)
    assert orga_content["count"] == orga_results
    if orga_results:
        assert "name" in orga_content["results"][0]


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
def test_orga_wrong_profile_page_update(orga_client, orga_user):
    response = orga_client.post(
        reverse("orga:user.view"), {"form": "tokennnnnn"}, follow=True
    )
    assert response.status_code == 200
    assert "trouble saving your input" in response.text


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
    assert "have been saved" in response.text
    orga_user.refresh_from_db()
    assert orga_user.name == "New name"
