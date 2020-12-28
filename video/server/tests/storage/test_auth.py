import datetime
import uuid

import jwt
import pytest


@pytest.mark.django_db
def test_no_auth_header(client):
    r = client.post("/storage/upload/", HTTP_HOST="localhost")
    assert r.status_code == 403


@pytest.mark.django_db
def test_invalid_token_header(client, world):
    r = client.post(
        "/storage/upload/", HTTP_AUTHORIZATION="Bearer", HTTP_HOST="localhost"
    )
    assert r.status_code == 403
    r = client.post(
        "/storage/upload/", HTTP_AUTHORIZATION="Bearer foo bar", HTTP_HOST="localhost"
    )
    assert r.status_code == 403


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
    r = client.post(
        "/storage/upload/", HTTP_AUTHORIZATION="Bearer " + token, HTTP_HOST="localhost"
    )
    assert r.status_code == 403


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
    r = client.post(
        "/storage/upload/", HTTP_AUTHORIZATION="Bearer " + token, HTTP_HOST="localhost"
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_no_permission(client, world):
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
    world.trait_grants = {"attendee": []}
    world.save()
    world.rooms.all().delete()
    token = jwt.encode(payload, config["secret"], algorithm="HS256")
    r = client.post(
        "/storage/upload/", HTTP_AUTHORIZATION="Bearer " + token, HTTP_HOST="localhost"
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_client_id(client, world, chat_room):
    token = str(uuid.uuid4())
    r = client.post(
        "/storage/upload/", HTTP_AUTHORIZATION="Client " + token, HTTP_HOST="localhost"
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_admin_token(client, world):
    config = world.config["JWT_secrets"][0]
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": config["issuer"],
        "aud": config["audience"],
        "exp": exp,
        "iat": iat,
        "uid": 123456,
        "traits": ["admin", "api", "chat.read", "foo.bar"],
    }
    token = jwt.encode(payload, config["secret"], algorithm="HS256")
    r = client.post(
        "/storage/upload/", HTTP_AUTHORIZATION="Bearer " + token, HTTP_HOST="localhost"
    )
    assert r.status_code == 400
