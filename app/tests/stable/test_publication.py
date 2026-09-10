from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import override_settings
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.api.serializers.event import EventSerializer
from eventyay.base.models import Device, Team
from eventyay.base.models.auth import StaffSession

@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_publication_controls_removed_from_main_settings(organizer_client, organizer, event):
    """The is_public and meta_noindex publication controls are no longer rendered on the
    event settings page; startpage_visible remains admin-only and absent as well."""
    url = reverse('eventyay_common:event.update', kwargs={
        'organizer': organizer.slug,
        'event': event.slug
    })
    response = organizer_client.get(url)
    assert response.status_code == 200
    assert b"is_public" not in response.content
    assert b"meta_noindex" not in response.content
    # startpage_visible must NOT appear in the organiser settings page (admin-only)
    assert b"startpage_visible" not in response.content

@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_publication_settings_save_via_main_settings(organizer_client, organizer, event):
    """Saving the main settings page works, keeps the event public by default, and does NOT
    change startpage_visible (there are no publication toggles to submit anymore)."""
    url = reverse('eventyay_common:event.update', kwargs={
        'organizer': organizer.slug,
        'event': event.slug
    })

    # Store original startpage_visible value before the request
    original_startpage_visible = event.startpage_visible

    response = organizer_client.get(url)
    form = response.context['form']
    sform = response.context['sform']
    
    # Assert initial choices are present
    assert 'en' in sform.initial.get('locales', [])
    assert len(sform.fields['locales'].choices) > 0

    # startpage_visible should not be a field the organiser form exposes
    assert 'startpage_visible' not in form.fields

    def build_post_data():
        return {
            'name_0': 'Test Event',
            'slug': event.slug,
            'date_from_0': '2026-10-01',
            'date_from_1': '10:00:00',
            'date_to_0': '2026-10-02',
            'date_to_1': '18:00:00',
            'email': event.email,
            'settings-timezone': 'UTC',
            'settings-locale': 'en',
            'settings-locales': ['en'],
            'header-links-TOTAL_FORMS': '0',
            'header-links-INITIAL_FORMS': '0',
            'header-links-MIN_NUM_FORMS': '0',
            'header-links-MAX_NUM_FORMS': '1000',
            'footer-links-TOTAL_FORMS': '0',
            'footer-links-INITIAL_FORMS': '0',
            'footer-links-MIN_NUM_FORMS': '0',
            'footer-links-MAX_NUM_FORMS': '1000',
        }

    response = organizer_client.post(url, build_post_data(), follow=True)

    if response.status_code == 200 and not response.redirect_chain:
        assert False, (
            f"Expected redirect after save, got form errors: "
            f"form={response.context['form'].errors} "
            f"sform={response.context['sform'].errors} "
            f"header_links_formset={response.context['header_links_formset'].errors} "
            f"footer_links_formset={response.context['footer_links_formset'].errors}"
        )

    assert response.status_code == 200
    assert len(response.redirect_chain) > 0, "Enable form submission did not redirect"
    
    event.refresh_from_db()
    event.settings.flush()
    # Events stay public by default even though there is no toggle to submit.
    assert event.is_public is True
    # startpage_visible must be unchanged — organisers cannot alter it
    assert event.startpage_visible == original_startpage_visible


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_organiser_cannot_change_startpage_visible_via_post(organizer_client, organizer, event):
    """Organisers cannot change startpage_visible by injecting the field into a POST request."""
    url = reverse('eventyay_common:event.update', kwargs={
        'organizer': organizer.slug,
        'event': event.slug
    })

    event.startpage_visible = False
    event.save(update_fields=['startpage_visible'])

    post_data = {
        'name_0': 'Test Event',
        'slug': event.slug,
        'date_from_0': '2026-10-01',
        'date_from_1': '10:00:00',
        'date_to_0': '2026-10-02',
        'date_to_1': '18:00:00',
        'email': event.email,
        'settings-timezone': 'UTC',
        'settings-locale': 'en',
        'settings-locales': ['en'],
        'header-links-TOTAL_FORMS': '0',
        'header-links-INITIAL_FORMS': '0',
        'header-links-MIN_NUM_FORMS': '0',
        'header-links-MAX_NUM_FORMS': '1000',
        'footer-links-TOTAL_FORMS': '0',
        'footer-links-INITIAL_FORMS': '0',
        'footer-links-MIN_NUM_FORMS': '0',
        'footer-links-MAX_NUM_FORMS': '1000',
        'startpage_visible': 'on',
    }

    response = organizer_client.post(url, post_data, follow=True)
    assert response.status_code == 200

    event.refresh_from_db()
    assert event.startpage_visible is False


STARTPAGE_FIELDS = ('startpage_visible', 'startpage_featured')


def _fake_request(event, *, user=None, auth=None, session_key='test-session-key'):
    return SimpleNamespace(
        user=user if user is not None else AnonymousUser(),
        auth=auth,
        event=event,
        session=SimpleNamespace(session_key=session_key),
    )


def _startpage_fields(event, request):
    with scopes_disabled():
        serializer = EventSerializer(event, context={'request': request})
        return {name: serializer.fields[name].read_only for name in STARTPAGE_FIELDS if name in serializer.fields}


@pytest.mark.django_db
def test_api_startpage_fields_hidden_for_organiser(event, user):
    """A normal organiser user can neither read nor write the start page fields."""
    user.is_staff = False
    user.is_superuser = False
    user.save(update_fields=['is_staff', 'is_superuser'])

    request = _fake_request(event, user=user)
    assert _startpage_fields(event, request) == {}

    with scopes_disabled():
        data = EventSerializer(event, context={'request': request}).data
    assert 'startpage_visible' not in data
    assert 'startpage_featured' not in data


@pytest.mark.django_db
def test_api_startpage_fields_hidden_for_team_api_token(event, organizer):
    """Organiser team API tokens have no access to the start page fields."""
    with scopes_disabled():
        team = Team.objects.create(
            organizer=organizer,
            name='Token team',
            all_events=True,
            can_change_event_settings=True,
            can_change_organizer_settings=True,
        )
        token = team.tokens.create(name='test-token')
        fields = _startpage_fields(event, _fake_request(event, auth=token, session_key=None))
    assert fields == {}


@pytest.mark.django_db
def test_api_startpage_fields_hidden_for_device(event, organizer):
    """Device tokens have no access to the start page fields."""
    with scopes_disabled():
        device = Device.objects.create(organizer=organizer, name='test-device', all_events=True)
        fields = _startpage_fields(event, _fake_request(event, auth=device, session_key=None))
    assert fields == {}


@pytest.mark.django_db
def test_api_startpage_fields_hidden_for_staff_without_active_session(event, user):
    """Staff status alone is not enough - an active staff session is required."""
    user.is_staff = True
    user.save(update_fields=['is_staff'])

    assert _startpage_fields(event, _fake_request(event, user=user)) == {}
    assert _startpage_fields(event, _fake_request(event, user=user, session_key=None)) == {}


@pytest.mark.django_db
def test_api_startpage_fields_writable_for_admin_with_active_session(event, user):
    """An admin with an active staff session sees the fields and may write them."""
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    StaffSession.objects.create(user=user, session_key='test-session-key', date_end=None, comment='')

    assert _startpage_fields(event, _fake_request(event, user=user)) == {
        'startpage_visible': False,
        'startpage_featured': False,
    }
