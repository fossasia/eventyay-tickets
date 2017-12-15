import json

import pytest
from django.core.management.base import CommandError
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


@pytest.mark.django_db
def test_schedule_single_ical_export(slot, client, schedule_schema):
    response = client.get(slot.submission.urls.ical, follow=True)
    assert response.status_code == 200

    content = response.content.decode()
    assert slot.submission.title in content


@pytest.mark.django_db
def test_feed_view(slot, client, schedule_schema):
    response = client.get(slot.submission.event.urls.feed)
    assert response.status_code == 200
    assert slot.submission.event.schedules.first().version in response.content.decode()


@pytest.mark.django_db
def test_html_export_event_required():
    from django.core.management import call_command
    with pytest.raises(CommandError) as excinfo:
        call_command('export_schedule_html')

    assert 'the following arguments are required: event' in str(excinfo)


@pytest.mark.django_db
def test_html_export_event_unknown():
    from django.core.management import call_command
    with pytest.raises(CommandError) as excinfo:
        call_command('export_schedule_html', 'foobar222')

    assert 'Could not find event with slug "foobar222"' in str(excinfo)


@pytest.mark.django_db
def test_html_export_language(event, slot):
    from django.core.management import call_command
    from django.conf import settings
    import os.path

    event.locale = 'de'
    event.save()
    call_command('export_schedule_html', event.slug)

    schedule_html = open(os.path.join(settings.HTMLEXPORT_ROOT, 'test', 'test/schedule/index.html')).read()
    assert 'Kontakt' in schedule_html


@pytest.mark.django_db
def test_html_export(event, other_event, slot, past_slot):
    from django.core.management import call_command
    from django.conf import settings
    import os.path

    call_command('export_schedule_html', event.slug)

    paths = [
        'static/common/img/logo.svg',
        'test/schedule/index.html',
        *[f'test/speaker/{speaker.code}/index.html' for speaker in slot.submission.speakers.all()],
        f'test/talk/{slot.submission.code}/index.html',
        *[f'test/speaker/{speaker.code}/index.html' for speaker in past_slot.submission.speakers.all()],
        f'test/talk/{past_slot.submission.code}/index.html',
    ]

    for path in paths:
        full_path = os.path.join(settings.HTMLEXPORT_ROOT, 'test', path)
        assert os.path.exists(full_path)

    assert not os.path.exists(os.path.join(settings.HTMLEXPORT_ROOT, 'test2')), "wrong event exported"

    # views and templates are the same for export and online viewing, so we just need a very basic test here
    talk_html = open(os.path.join(settings.HTMLEXPORT_ROOT, 'test', f'test/talk/{past_slot.submission.code}/index.html')).read()
    assert talk_html.count(past_slot.submission.title) >= 2

    speaker = slot.submission.speakers.all()[0]
    speaker_html = open(os.path.join(settings.HTMLEXPORT_ROOT, 'test', f'test/speaker/{speaker.code}/index.html')).read()
    assert speaker.name in speaker_html

    schedule_html = open(os.path.join(settings.HTMLEXPORT_ROOT, 'test', f'test/schedule/index.html')).read()
    assert 'Contact us' in schedule_html  # locale
    assert past_slot.submission.title in schedule_html
