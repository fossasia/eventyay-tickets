import pytest
from django.urls import reverse
from lxml import etree


@pytest.mark.django_db
def test_schedule_export(slot, client, schedule_schema):
    response = client.get(reverse(f'agenda:frab-xml', kwargs={'event': slot.submission.event.slug}), follow=True)
    assert response.status_code == 200

    content = response.content.decode()
    assert slot.submission.title in content

    parser = etree.XMLParser(schema=schedule_schema)
    etree.fromstring(response.content, parser)  # Will raise if the schedule does not match the schema
