import pytest
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import jwt
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from eventyay.features.integrations.zoom.views import MeetingView, generate_signature
from eventyay.features.live.modules.zoom import ZoomModule


@pytest.mark.django_db
def test_generate_signature_payload_and_types():
    # Modern Zoom Meeting SDK requires integer epoch timestamps and sdkKey/appKey
    secret = "my_client_secret_at_least_32_bytes_long_123"
    sig = generate_signature("my_client_id", secret, 1234567890, role=0)
    assert sig != ""
    decoded = jwt.decode(sig, secret, algorithms=["HS256"])
    assert decoded["sdkKey"] == "my_client_id"
    assert decoded["appKey"] == "my_client_id"
    assert decoded["mn"] == "1234567890"
    assert decoded["role"] == 0
    assert isinstance(decoded["iat"], int)
    assert isinstance(decoded["exp"], int)
    assert isinstance(decoded["tokenExp"], int)
    assert decoded["exp"] > decoded["iat"]

    # Missing credentials return empty string gracefully
    assert generate_signature("", secret, 123) == ""
    assert generate_signature("key", "", 123) == ""


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_zoom_module_url_parsing_and_token(event, user):
    user.profile = {"display_name": "Test User"}
    consumer = MagicMock()
    consumer.user = user
    consumer.event = event
    event.domain = ""  # Test relative path fallback
    consumer.send_success = AsyncMock()

    # Unwrapped func to test URL and query extraction logic directly
    core_room_url = ZoomModule.room_url.__wrapped__.__wrapped__

    # 1. Plain meeting ID with spaces
    module = ZoomModule(consumer=consumer)
    module.module_config = {
        "meeting_number": "123 456 7890",
        "password": "pass",
        "disable_chat": True,
    }
    await core_room_url(module, {})
    assert consumer.send_success.called
    result_url = consumer.send_success.call_args[0][0]["url"]
    assert result_url.startswith("/zoom/meeting/?data=")
    query_data = parse_qs(urlparse(result_url).query)["data"][0]
    payload = signing.loads(query_data)
    assert payload["mn"] == 1234567890
    assert payload["pw"] == "pass"
    assert payload["dc"] is True
    assert payload["event_id"] == str(event.id)

    # 2. Full Zoom URL with embedded meeting ID and passcode
    module.module_config = {
        "meeting_number": "https://us02web.zoom.us/j/98765432109?pwd=testpasscode123",
        "password": "",  # Empty, should auto-extract from URL
    }
    await core_room_url(module, {})
    result_url = consumer.send_success.call_args[0][0]["url"]
    assert result_url.startswith("/zoom/meeting/?data=")
    query_data = parse_qs(urlparse(result_url).query)["data"][0]
    payload = signing.loads(query_data)
    assert payload["mn"] == 98765432109
    assert payload["pw"] == "testpasscode123"

    # 3. Domain-backed URL
    event.domain = "live.example.com"
    await core_room_url(module, {})
    result_url = consumer.send_success.call_args[0][0]["url"]
    assert result_url.startswith("//live.example.com/zoom/meeting/?data=")


@pytest.mark.django_db
def test_meeting_view_with_modern_join_links(event, user):
    rf = RequestFactory()
    secret = "test_sdk_secret_with_32_bytes_length_here!"

    data = signing.dumps(
        {
            "mn": 88877766655,
            "pw": "supersecret",
            "un": "Alice Walker",
            "ho": False,
            "ui": str(user.pk),
            "dc": False,
            "event_id": str(event.id),
            "client_id": "test_sdk_key",
            "client_secret": secret,
        }
    )

    request = rf.get(f"/zoom/meeting/?data={data}")
    request.user = user
    view = MeetingView()
    view.setup(request)

    ctx = view.get_context_data()
    assert ctx["meeting_number"] == "88877766655"
    assert ctx["password"] == "supersecret"
    assert ctx["user_name"] == "Alice Walker"
    assert ctx["has_sdk_credentials"] is True
    assert "zoommtg://zoom.us/join?confno=88877766655&pwd=supersecret" in ctx["zoom_app_url"]
    assert "https://zoom.us/wc/88877766655/join?pwd=supersecret" in ctx["zoom_web_url"]
    assert ctx["zoom_join_url"] == "https://zoom.us/j/88877766655?pwd=supersecret"
    assert ctx["signature"] != ""

    # Test rendering template
    response = view.render_to_response(ctx)
    content = response.rendered_content
    assert "88877766655" in content
    assert "supersecret" in content
    assert "Open in Zoom App" in content
    assert "Leave" in content
    assert "zoom-embedded-frame" in content
    assert "https://source.zoom.us/3.11.2/" in content
    assert 'target="_blank"' not in content


@pytest.mark.django_db
def test_meeting_view_fallback_without_sdk_credentials(event, user):
    rf = RequestFactory()

    data = signing.dumps(
        {
            "mn": 11122233344,
            "pw": "mypass",
            "un": "Bob Builder",
            "ho": False,
            "ui": str(user.pk),
            "dc": True,
            "event_id": str(event.id),
            "client_id": "",
            "client_secret": "",
        }
    )

    request = rf.get(f"/zoom/meeting/?data={data}")
    request.user = user
    view = MeetingView()
    view.setup(request)

    ctx = view.get_context_data()
    assert ctx["has_sdk_credentials"] is False
    assert ctx["signature"] == ""
    assert ctx["zoom_app_url"].startswith("zoommtg://zoom.us/join?confno=11122233344")

    response = view.render_to_response(ctx)
    content = response.rendered_content
    # When SDK credentials are absent, the embedded iframe is rendered directly in the room player
    assert "zoom-embedded-frame" in content
    assert "11122233344" in content
    assert "https://zoom.us/wc/11122233344/join" in content
    assert "https://source.zoom.us/3.11.2/" not in content
    assert 'target="_blank"' not in content


@pytest.mark.django_db
def test_meeting_view_rejects_tampered_data(event, user):
    rf = RequestFactory()
    request = rf.get("/zoom/meeting/?data=tampered_invalid_token")
    request.user = user
    view = MeetingView()
    view.setup(request)

    with pytest.raises(PermissionDenied):
        view.get_context_data()


@pytest.mark.django_db
def test_meeting_view_allows_iframe_embedding(event, user):
    from django.test import Client

    data = signing.dumps(
        {
            "mn": 1234567890,
            "pw": "test",
            "un": "Tester",
            "ho": False,
            "ui": str(user.pk),
            "dc": False,
            "event_id": str(event.id),
        }
    )
    client = Client()
    resp = client.get(f"/zoom/meeting/?data={data}", HTTP_HOST="localhost:8000")
    assert resp.status_code == 200
    # Must not have X-Frame-Options: DENY so it can embed inside the video room iframe
    assert resp.headers.get("X-Frame-Options") is None
    assert getattr(resp, "xframe_options_exempt", False) is True


@pytest.mark.django_db
def test_meeting_ended_view_returns_to_attendee_dashboard(event):
    from django.test import Client

    client = Client()
    resp = client.get("/zoom/ended/", HTTP_HOST="localhost:8000")
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "Meeting Ended" in content
    assert "Return to Dashboard" in content
    assert "/about" in content
    assert "zoom:leave" in content
