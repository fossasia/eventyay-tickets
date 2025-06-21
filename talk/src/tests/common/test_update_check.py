import json
from datetime import timedelta

import pytest
import responses
from django.core import mail as djmail
from django.utils.timezone import now

from pretalx import __version__
from pretalx.common.models.settings import GlobalSettings
from pretalx.common.update_check import (
    check_result_table,
    run_update_check,
    update_check,
)


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


def request_callback_with_plugin(request):
    json_data = json.loads(request.body.decode())
    resp_body = {
        "status": "ok",
        "version": {
            "latest": "1.0.0",
            "yours": json_data.get("version"),
            "updatable": True,
        },
        "plugins": {"tests": {"latest": "1.1.1", "updatable": True}},
    }
    return 200, {"Content-Type": "text/json"}, json.dumps(resp_body)


def request_callback_not_updatable(request):
    json_data = json.loads(request.body.decode())
    resp_body = {
        "status": "ok",
        "version": {
            "latest": "1.0.0",
            "yours": json_data.get("version"),
            "updatable": False,
        },
        "plugins": {},
    }
    return 200, {"Content-Type": "text/json"}, json.dumps(resp_body)


def request_callback_disallowed(request):  # pragma: no cover
    pytest.fail("Request issued even though none should be issued.")


@pytest.mark.django_db
@responses.activate
def test_update_check_disabled():
    gs = GlobalSettings()
    gs.settings.update_check_enabled = False

    responses.add_callback(
        responses.POST,
        "https://pretalx.com/.update_check/",
        callback=request_callback_disallowed,
        content_type="application/json",
    )
    update_check.apply(throw=True)
    run_update_check(None)


@pytest.mark.django_db
@responses.activate
def test_update_check_sent_no_updates():
    responses.add_callback(
        responses.POST,
        "https://pretalx.com/.update_check/",
        callback=request_callback_not_updatable,
        content_type="application/json",
    )
    update_check.apply(throw=True)
    gs = GlobalSettings()
    assert not gs.settings.update_check_result_warning
    storeddata = gs.settings.update_check_result
    assert not storeddata["version"]["updatable"]


@pytest.mark.django_db
@responses.activate
def test_update_check_sent_updates():
    responses.add_callback(
        responses.POST,
        "https://pretalx.com/.update_check/",
        callback=request_callback_updatable,
        content_type="application/json",
    )
    update_check.apply(throw=True)
    gs = GlobalSettings()
    assert gs.settings.update_check_result_warning
    storeddata = gs.settings.update_check_result
    assert storeddata["version"]["updatable"]


@pytest.mark.django_db
@responses.activate
def test_update_check_mail_sent():
    gs = GlobalSettings()
    gs.settings.update_check_email = "test@example.com"

    responses.add_callback(
        responses.POST,
        "https://pretalx.com/.update_check/",
        callback=request_callback_updatable,
        content_type="application/json",
    )
    update_check.apply(throw=True)

    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ["test@example.com"]
    assert "update" in djmail.outbox[0].subject


@pytest.mark.django_db
@responses.activate
def test_update_check_mail_sent_only_after_change():
    gs = GlobalSettings()
    gs.settings.update_check_email = "test@example.com"

    with responses.RequestsMock() as rsps:
        rsps.add_callback(
            responses.POST,
            "https://pretalx.com/.update_check/",
            callback=request_callback_updatable,
            content_type="application/json",
        )

        update_check.apply(throw=True)
        assert len(djmail.outbox) == 1

        update_check.apply(throw=True)
        assert len(djmail.outbox) == 1

    with responses.RequestsMock() as rsps:
        rsps.add_callback(
            responses.POST,
            "https://pretalx.com/.update_check/",
            callback=request_callback_not_updatable,
            content_type="application/json",
        )

        update_check.apply(throw=True)
        assert len(djmail.outbox) == 1

    with responses.RequestsMock() as rsps:
        rsps.add_callback(
            responses.POST,
            "https://pretalx.com/.update_check/",
            callback=request_callback_updatable,
            content_type="application/json",
        )

        update_check.apply(throw=True)
        assert len(djmail.outbox) == 2


@pytest.mark.django_db
def test_update_cron_interval(monkeypatch):
    called = False

    def callee():
        nonlocal called
        called = True

    monkeypatch.setattr(update_check, "apply_async", callee)

    gs = GlobalSettings()
    gs.settings.update_check_email = "test@example.com"

    gs.settings.update_check_last = now() - timedelta(hours=14)
    run_update_check(None)
    assert not called

    gs.settings.update_check_last = now() - timedelta(hours=24)
    run_update_check(None)
    assert called


@pytest.mark.django_db
def test_result_table_empty():
    assert check_result_table() == {"error": "no_result"}


@pytest.mark.django_db
def test_result_table_with_error():
    gs = GlobalSettings()
    gs.settings.update_check_result = '{"error": "errororor"}'
    assert check_result_table() == {"error": "errororor"}


@responses.activate
@pytest.mark.django_db
def test_result_table_up2date():
    responses.add_callback(
        responses.POST,
        "https://pretalx.com/.update_check/",
        callback=request_callback_not_updatable,
        content_type="application/json",
    )
    update_check.apply(throw=True)
    tbl = check_result_table()
    assert tbl[0] == ("pretalx", __version__, "1.0.0", False)
    plugin = [e for e in tbl if e[0] == "Plugin: test plugin for pretalx"][0]
    assert plugin
    assert plugin[2] == "?"


@responses.activate
@pytest.mark.django_db
def test_result_table_up2date_with_plugins():
    responses.add_callback(
        responses.POST,
        "https://pretalx.com/.update_check/",
        callback=request_callback_with_plugin,
        content_type="application/json",
    )
    update_check.apply(throw=True)
    tbl = check_result_table()
    assert tbl[0] == ("pretalx", __version__, "1.0.0", True)
    line = [
        e
        for e in tbl
        if e == ("Plugin: test plugin for pretalx", "0.0.0", "1.1.1", True)
    ]
    assert line
