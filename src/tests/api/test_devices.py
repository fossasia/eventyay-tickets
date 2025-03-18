import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled
from jsonschema import validate

from pretix.base.models import Device

@pytest.fixture
def device(organizer, event):
    t = organizer.devices.create(
        device_id=1,
        name='Scanner',
        hardware_brand="Zebra",
        unique_serial="UOS3GNZ27O39V3QS",
        initialization_token="frkso3m2w58zuw70",
        hardware_model="TC25",
        software_brand="pretixSCAN",
        software_version="1.5.1",
        initialized=now(),
        all_events=False,
    )
    t.limit_events.add(event)
    return t

DEVICE_SCHEMA = {
    "type": "object",
    "properties": {
        "device_id": {"type": "integer"},
        "unique_serial": {"type": "string"},
        "initialization_token": {"type": "string"},
        "all_events": {"type": "boolean"},
        "limit_events": {"type": "array"},
        "revoked": {"type": "boolean"},
        "name": {"type": "string"},
        "created": {"type": "string", "format": "date-time"},
        "initialized": {"type": "string", "format": "date-time"},
        "hardware_brand": {"type": "string"},
        "hardware_model": {"type": "string"},
        "software_brand": {"type": "string"},
        "software_version": {"type": "string"},
        "security_profile": {"type": "string"}
    },
    "required": ["device_id", "unique_serial", "name", "hardware_brand"]
}

@pytest.mark.django_db
def test_device_list(token_client, organizer, event, device):
    resp = token_client.get(f'/api/v1/organizers/{organizer.slug}/devices/')
    assert resp.status_code == 200
    assert "results" in resp.data
    for dev in resp.data["results"]:
        validate(dev, DEVICE_SCHEMA)

@pytest.mark.django_db
def test_device_detail(token_client, organizer, event, device):
    resp = token_client.get(f'/api/v1/organizers/{organizer.slug}/devices/{device.device_id}/')
    assert resp.status_code == 200
    validate(resp.data, DEVICE_SCHEMA)

@pytest.mark.django_db
def test_device_create(token_client, organizer, event):
    payload = {
        "name": "Foobar",
        "all_events": False,
        "limit_events": ["dummy"],
    }
    resp = token_client.post(f'/api/v1/organizers/{organizer.slug}/devices/', payload, format='json')
    assert resp.status_code == 201
    with scopes_disabled():
        d = Device.objects.get(device_id=resp.data['device_id'])
        assert list(d.limit_events.all()) == [event]
        assert d.initialization_token
        assert not d.initialized

@pytest.mark.django_db
def test_device_create_missing_fields(token_client, organizer, event):
    resp = token_client.post(f'/api/v1/organizers/{organizer.slug}/devices/', {}, format='json')
    assert resp.status_code == 400
    assert "name" in resp.data

@pytest.mark.django_db
def test_device_update(token_client, organizer, event, device):
    resp = token_client.patch(f'/api/v1/organizers/{organizer.slug}/devices/{device.device_id}/',
        {"name": "bla", "hardware_brand": "Foo"}, format='json')
    assert resp.status_code == 200
    device.refresh_from_db()
    assert device.hardware_brand == 'Foo'
    assert device.name == 'bla'

@pytest.mark.django_db
def test_device_soft_delete(token_client, organizer, event, device):
    resp = token_client.delete(f'/api/v1/organizers/{organizer.slug}/devices/{device.device_id}/')
    assert resp.status_code == 405
    device.refresh_from_db()
    assert device.revoked is False
