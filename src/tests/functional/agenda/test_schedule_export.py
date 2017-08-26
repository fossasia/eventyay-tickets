import json

import pytest
from django.urls import reverse
from lxml import etree


@pytest.mark.django_db
def test_schedule_frab_xml_export(slot, client, schedule_schema):
    response = client.get(reverse(f'agenda:frab-xml', kwargs={'event': slot.submission.event.slug}), follow=True)
    assert response.status_code == 200

    content = response.content.decode()
    assert slot.submission.title in content

    parser = etree.XMLParser(schema=schedule_schema)
    etree.fromstring(response.content, parser)  # Will raise if the schedule does not match the schema


@pytest.mark.django_db
def test_schedule_frab_json_export(slot, client, schedule_schema):
    response = client.get(reverse(f'agenda:frab-json', kwargs={'event': slot.submission.event.slug}), follow=True)
    assert response.status_code == 200

    content = response.content.decode()
    assert slot.submission.title in content

    parsed_content = json.loads(content)
    print(parsed_content['schedule'].keys())
    assert parsed_content['schedule']


@pytest.mark.django_db
def test_schedule_frab_xcal_export(slot, client, schedule_schema):
    response = client.get(reverse(f'agenda:frab-xcal', kwargs={'event': slot.submission.event.slug}), follow=True)
    assert response.status_code == 200

    content = response.content.decode()
    assert slot.submission.title in content


@pytest.mark.django_db
def test_schedule_ical_export(slot, client, schedule_schema):
    response = client.get(reverse(f'agenda:ical', kwargs={'event': slot.submission.event.slug}), follow=True)
    assert response.status_code == 200

    content = response.content.decode()
    assert slot.submission.title in content
