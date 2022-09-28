import datetime

import jwt
import pytest

from ..utils import get_token


@pytest.mark.django_db
def test_no_auth_header(client):
    r = client.get("/api/v1/worlds/sample/rooms/")
    assert r.status_code == 403
    assert r.data["detail"] == "Authentication credentials were not provided."


@pytest.mark.django_db
def test_invalid_token_header(client, world):
    r = client.get("/api/v1/worlds/sample/rooms/", HTTP_AUTHORIZATION="Bearer")
    assert r.status_code == 403
    assert r.data["detail"] == "Invalid token header. No credentials provided."
    r = client.get("/api/v1/worlds/sample/rooms/", HTTP_AUTHORIZATION="Bearer foo bar")
    assert r.status_code == 403
    assert (
        r.data["detail"]
        == "Invalid token header. Token string should not contain spaces."
    )
    r = client.get(
        "/api/v1/worlds/sample/rooms/",
        HTTP_AUTHORIZATION=b"Bearer F\xc3\xb8\xc3\xb6\xbbB\xc3\xa5r",
    )
    assert r.status_code == 403
    assert (
        r.data["detail"]
        == "Invalid token header. Token string should not contain invalid characters."
    )
    r = client.get("/api/v1/worlds/sample/rooms/", HTTP_AUTHORIZATION=b"Bearer F")
    assert r.status_code == 403
    assert r.data["detail"] == "Invalid token."


@pytest.mark.django_db
def test_non_existing_world(client):
    r = client.get("/api/v1/worlds/bogus/rooms/", HTTP_AUTHORIZATION="Bearer Foobar")
    assert r.status_code == 404


@pytest.mark.django_db
def test_invalid_token(client, world):
    config = world.config["JWT_secrets"][0]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": 123456,
        "traits": ["chat.read", "foo.bar"],
    }
    token = jwt.encode(payload, config["secret"] + "aaaa", algorithm="HS256")
    r = client.get("/api/v1/worlds/sample/rooms/", HTTP_AUTHORIZATION="Bearer " + token)
    assert r.status_code == 403
    assert r.data["detail"] == "Invalid token."


@pytest.mark.django_db
def test_expired_token(client, world):
    config = world.config["JWT_secrets"][0]
    iat = datetime.datetime.utcnow()
    exp = iat - datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": 123456,
        "traits": ["chat.read", "foo.bar"],
    }
    token = jwt.encode(payload, config["secret"], algorithm="HS256")
    r = client.get("/api/v1/worlds/sample/rooms/", HTTP_AUTHORIZATION="Bearer " + token)
    assert r.status_code == 403
    assert r.data["detail"] == "Invalid token."


@pytest.mark.django_db
def test_no_admin_token(client, world):
    token = get_token(world, ["chat.read", "foo.bar"])
    r = client.get("/api/v1/worlds/sample/rooms/", HTTP_AUTHORIZATION="Bearer " + token)
    assert r.status_code == 403
    assert r.data["detail"] == "You do not have permission to perform this action."


@pytest.mark.django_db
def test_admin_token(client, world):
    token = get_token(world, ["admin", "api", "chat.read", "foo.bar"])
    r = client.get("/api/v1/worlds/sample/rooms/", HTTP_AUTHORIZATION="Bearer " + token)
    assert r.status_code == 200


@pytest.mark.django_db
def test_admin_delete_user(client, world, event_user):
    token = get_token(world, ["admin"])
    r = client.post(
        "/api/v1/worlds/sample/delete_user",
        HTTP_AUTHORIZATION="Bearer " + token,
        data={"user_id": str(event_user.id)},
    )
    assert r.status_code == 204
    event_user.refresh_from_db()
    assert event_user.deleted is True


@pytest.mark.django_db
def test_admin_delete_user_unknown_user(client, world, event_user):
    token = get_token(world, ["admin"])
    r = client.post(
        "/api/v1/worlds/sample/delete_user",
        HTTP_AUTHORIZATION="Bearer " + token,
        data={"user_id": str(event_user.id) + "foo"},
    )
    assert r.status_code == 404
    event_user.refresh_from_db()
    assert event_user.deleted is False


@pytest.mark.django_db
def test_admin_delete_user_no_access(client, world, event_user):
    token = get_token(world, ["noadmin"])
    r = client.post(
        "/api/v1/worlds/sample/delete_user",
        HTTP_AUTHORIZATION="Bearer " + token,
        data={"user_id": str(event_user.id)},
    )
    assert r.status_code == 403
    event_user.refresh_from_db()
    assert event_user.deleted is False


@pytest.mark.django_db
def test_admin_delete_user_missing_id(client, world, event_user):
    token = get_token(world, ["admin"])
    r = client.post(
        "/api/v1/worlds/sample/delete_user",
        HTTP_AUTHORIZATION="Bearer " + token,
        data={"user": str(event_user.id)},
    )
    assert r.status_code == 401
    event_user.refresh_from_db()
    assert event_user.deleted is False
