from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled
from PIL import Image

from eventyay.base.meetup import (
    get_rsvp_product_and_quota,
    has_video_stream,
    is_meetup_event,
)
from eventyay.base.models import Event, Team, User
from eventyay.base.settings import GlobalSettingsObject


@pytest.fixture
def orga_client(client, organizer):
    GlobalSettingsObject().settings.set('meetup_creation_enabled', True)
    user = User.objects.create_superuser('organizer_user@test.org', 'testpass123')
    team = Team.objects.create(
        organizer=organizer,
        all_events=True,
        can_create_events=True,
        can_change_teams=True,
        can_change_organizer_settings=True,
        can_change_event_settings=True,
        can_change_items=True,
        can_view_orders=True,
        can_change_orders=True,
        can_view_vouchers=True,
        can_change_vouchers=True,
    )
    team.members.add(user)
    client.force_login(user)
    user.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    return client


def _create_test_image():
    out = BytesIO()
    im = Image.new('RGB', (800, 450), color=(73, 109, 137))
    im.save(out, format='PNG')
    out.seek(0)
    return SimpleUploadedFile('test_cover.png', out.read(), content_type='image/png')


@pytest.mark.django_db
def test_meetup_create_get_renders_meetup_template(orga_client):
    url = reverse('eventyay_common:events.add') + '?meetup=1'
    response = orga_client.get(url)
    assert response.status_code == 200
    assert 'eventyay_common/events/meetup_create.html' in [t.name for t in response.templates]


@pytest.mark.django_db
def test_standard_event_create_get_renders_standard_template(orga_client):
    url = reverse('eventyay_common:events.add')
    response = orga_client.get(url)
    assert response.status_code == 200
    assert 'eventyay_common/events/create.html' in [t.name for t in response.templates]


@pytest.mark.django_db
def test_meetup_create_post_success_in_person_unlimited(orga_client, organizer):
    url = reverse('eventyay_common:events.add')
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'PyData Meetup',
        'basics-date_from_0': '2026-10-15',
        'basics-date_from_1': '18:00:00',
        'basics-date_to_0': '2026-10-15',
        'basics-date_to_1': '20:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Tech Hub Hall A',
        'basics-capacity_type': 'unlimited',
    }
    response = orga_client.post(url, data)
    assert response.status_code == 302

    with scopes_disabled():
        event = Event.objects.filter(organizer=organizer, name__icontains='PyData Meetup').first()
        assert event is not None
        assert str(event.name) == 'PyData Meetup'
        assert is_meetup_event(event) is True
        assert event.live is True
        assert event.tickets_published is True
        assert bool(event.slug) is True  # Slug auto-generated

        product, quota = get_rsvp_product_and_quota(event)
        assert product is not None
        assert quota is not None
        assert quota.size is None


@pytest.mark.django_db
def test_meetup_create_post_with_description_and_capacity_limit(orga_client, organizer):
    url = reverse('eventyay_common:events.add')
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'AI Builders Night',
        'basics-date_from_0': '2026-11-01',
        'basics-date_from_1': '19:00:00',
        'basics-date_to_0': '2026-11-01',
        'basics-date_to_1': '21:00:00',
        'basics-timezone': 'UTC',
        'basics-frontpage_text_0': 'Join us for talks on modern generative agents and tooling.',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Innovation Center',
        'basics-capacity_type': 'limited',
        'basics-registration_limit': 60,
    }
    response = orga_client.post(url, data)
    assert response.status_code == 302

    with scopes_disabled():
        event = Event.objects.filter(organizer=organizer, name__icontains='AI Builders Night').first()
        assert event is not None
        assert str(event.name) == 'AI Builders Night'
        assert is_meetup_event(event) is True
        assert str(event.settings.frontpage_text) == 'Join us for talks on modern generative agents and tooling.'

        product, quota = get_rsvp_product_and_quota(event)
        assert quota is not None
        assert quota.size == 60


@pytest.mark.django_db
def test_meetup_create_post_virtual_with_video_stream(orga_client, organizer):
    url = reverse('eventyay_common:events.add')
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Global Online Tech Talk',
        'basics-date_from_0': '2026-12-05',
        'basics-date_from_1': '17:00:00',
        'basics-date_to_0': '2026-12-05',
        'basics-date_to_1': '18:30:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'virtual',
        'basics-location_0': '123 Physical Street',
        'basics-geo_lat': '40.712800',
        'basics-geo_lon': '-74.006000',
        'basics-video_type': 'youtube',
        'basics-video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'basics-capacity_type': 'unlimited',
    }
    response = orga_client.post(url, data)
    assert response.status_code == 302

    with scopes_disabled():
        event = Event.objects.filter(organizer=organizer, name__icontains='Global Online Tech Talk').first()
        assert event is not None
        assert str(event.name) == 'Global Online Tech Talk'
        assert is_meetup_event(event) is True
        assert has_video_stream(event) is True
        assert event.settings.meetup_video_active is True
        assert not event.location
        assert event.geo_lat is None
        assert event.geo_lon is None


@pytest.mark.django_db
def test_meetup_create_post_with_cover_image(orga_client, organizer):
    url = reverse('eventyay_common:events.add')
    test_image = _create_test_image()
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Design Systems Meetup',
        'basics-date_from_0': '2026-10-20',
        'basics-date_from_1': '18:00:00',
        'basics-date_to_0': '2026-10-20',
        'basics-date_to_1': '20:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Design Studio 4B',
        'basics-capacity_type': 'unlimited',
        'basics-logo_image': test_image,
    }
    response = orga_client.post(url, data)
    assert response.status_code == 302

    with scopes_disabled():
        event = Event.objects.filter(organizer=organizer, name__icontains='Design Systems Meetup').first()
        assert event is not None
        assert str(event.name) == 'Design Systems Meetup'
        assert is_meetup_event(event) is True
        header_img = event.settings.get('logo_image', as_type=str, default='')
        assert header_img.startswith('file://')
        assert bool(event.visible_header_image_url) is True


@pytest.mark.django_db
def test_meetup_create_validation_errors(orga_client, organizer):
    url = reverse('eventyay_common:events.add')

    # Video type provided but URL missing
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Invalid Virtual Meetup',
        'basics-date_from_0': '2026-10-20',
        'basics-date_from_1': '18:00:00',
        'basics-date_to_0': '2026-10-20',
        'basics-date_to_1': '20:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'virtual',
        'basics-video_type': 'youtube',
        'basics-video_url': '',
        'basics-capacity_type': 'unlimited',
    }
    response = orga_client.post(url, data)
    assert response.status_code == 200
    assert 'basics_form' in response.context
    assert 'video_url' in response.context['basics_form'].errors

    # Limited capacity missing registration limit
    data_limited = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Invalid Capacity Meetup',
        'basics-date_from_0': '2026-10-20',
        'basics-date_from_1': '18:00:00',
        'basics-date_to_0': '2026-10-20',
        'basics-date_to_1': '20:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Room 1',
        'basics-capacity_type': 'limited',
        'basics-registration_limit': '',
    }
    response_limited = orga_client.post(url, data_limited)
    assert response_limited.status_code == 200
    assert 'registration_limit' in response_limited.context['basics_form'].errors


@pytest.mark.django_db
def test_meetup_create_post_public_default(orga_client, organizer):
    url = reverse('eventyay_common:events.add')
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Public Meetup Test',
        'basics-date_from_0': '2026-10-15',
        'basics-date_from_1': '18:00:00',
        'basics-date_to_0': '2026-10-15',
        'basics-date_to_1': '20:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Community Hall',
        'basics-capacity_type': 'unlimited',
        'basics-privacy_type': 'public',
    }
    response = orga_client.post(url, data)
    assert response.status_code == 302

    with scopes_disabled():
        event = Event.objects.filter(organizer=organizer, name__icontains='Public Meetup Test').first()
        assert event is not None
        assert is_meetup_event(event) is True
        assert event.live is True
        assert event.tickets_published is True
        assert event.is_public is True
        assert event.private_testmode is False
        assert event.testmode is False
        assert event.settings.get('private_testmode_tickets', as_type=bool) is False


@pytest.mark.django_db
def test_meetup_create_post_private_mode(orga_client, organizer):
    url = reverse('eventyay_common:events.add')
    data = {
        'is_meetup': 'on',
        'foundation-organizer': organizer.pk,
        'foundation-locales': ['en'],
        'basics-locale': 'en',
        'basics-name_0': 'Private Meetup Test',
        'basics-date_from_0': '2026-10-15',
        'basics-date_from_1': '18:00:00',
        'basics-date_to_0': '2026-10-15',
        'basics-date_to_1': '20:00:00',
        'basics-timezone': 'UTC',
        'basics-location_type': 'in_person',
        'basics-location_0': 'Internal Boardroom',
        'basics-capacity_type': 'unlimited',
        'basics-privacy_type': 'private',
    }
    response = orga_client.post(url, data)
    assert response.status_code == 302

    with scopes_disabled():
        event = Event.objects.filter(organizer=organizer, name__icontains='Private Meetup Test').first()
        assert event is not None
        assert is_meetup_event(event) is True
        assert event.live is True
        assert event.tickets_published is True
        assert event.is_public is False
        assert event.private_testmode is False
        assert event.settings.get('meta_noindex', as_type=bool) is True
