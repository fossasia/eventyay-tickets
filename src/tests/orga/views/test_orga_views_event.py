import json

import pytest
from django.conf import settings
from django.core import mail as djmail

from pretalx.event.models import Event


@pytest.mark.django_db
def test_edit_mail_settings(orga_client, event, availability):
    assert event.settings.mail_from != 'foo@bar.com'
    assert event.settings.smtp_port != '25'
    response = orga_client.get(event.orga_urls.mail_settings, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        event.orga_urls.mail_settings,
        follow=True,
        data={
            'mail_from': 'foo@bar.com',
            'smtp_host': 'localhost',
            'smtp_password': '',
            'smtp_port': '25',
        },
    )
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    assert event.settings.mail_from == 'foo@bar.com'
    assert event.settings.smtp_port == 25


@pytest.mark.django_db
def test_fail_unencrypted_mail_settings(orga_client, event, availability):
    assert event.settings.mail_from != 'foo@bar.com'
    assert event.settings.smtp_port != '25'
    response = orga_client.get(event.orga_urls.mail_settings, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        event.orga_urls.mail_settings,
        follow=True,
        data={
            'mail_from': 'foo@bar.com',
            'smtp_host': 'foo.bar.com',
            'smtp_password': '',
            'smtp_port': '25',
        },
    )
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    assert event.settings.mail_from != 'foo@bar.com'
    assert event.settings.smtp_port != 25


@pytest.mark.django_db
def test_test_mail_settings(orga_client, event, availability):
    assert event.settings.mail_from != 'foo@bar.com'
    assert event.settings.smtp_port != '25'
    response = orga_client.get(event.orga_urls.mail_settings, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        event.orga_urls.mail_settings,
        follow=True,
        data={
            'mail_from': 'foo@bar.com',
            'smtp_host': 'localhost',
            'smtp_password': '',
            'smtp_port': '25',
            'smtp_use_custom': '1',
            'test': '1',
        },
    )
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    assert event.settings.mail_from == 'foo@bar.com'
    assert event.settings.smtp_port == 25


@pytest.mark.django_db
@pytest.mark.parametrize(
    'path,allowed',
    (
        ('tests/fixtures/custom.css', True),
        ('tests/fixtures/malicious.css', False),
        ('tests/conftest.py', False),
    ),
)
def test_add_custom_css(event, orga_client, path, allowed):
    assert not event.custom_css
    with open(path, 'r') as custom_css:
        response = orga_client.post(
            event.orga_urls.edit_settings,
            {
                'name_0': event.name,
                'slug': 'csstest',
                'locales': ','.join(event.locales),
                'locale': event.locale,
                'date_from': event.date_from,
                'date_to': event.date_to,
                'timezone': event.timezone,
                'email': event.email or '',
                'primary_color': event.primary_color or '',
                'custom_css': custom_css,
            },
            follow=True,
        )
    event.refresh_from_db()
    assert response.status_code == 200
    assert bool(event.custom_css) == allowed


@pytest.mark.django_db
@pytest.mark.parametrize(
    'path',
    (
        'tests/fixtures/custom.css',
        'tests/fixtures/malicious.css',
        'tests/conftest.py',
    ),
)
def test_add_custom_css_as_administrator(event, administrator_client, path):
    assert not event.custom_css
    with open(path, 'r') as custom_css:
        response = administrator_client.post(
            event.orga_urls.edit_settings,
            {
                'name_0': event.name,
                'slug': 'csstest',
                'locales': ','.join(event.locales),
                'locale': event.locale,
                'date_from': event.date_from,
                'date_to': event.date_to,
                'timezone': event.timezone,
                'email': event.email,
                'primary_color': event.primary_color or '',
                'custom_css': custom_css,
            },
            follow=True,
        )
    event.refresh_from_db()
    assert response.status_code == 200
    assert event.custom_css


@pytest.mark.django_db
def test_add_logo(event, orga_client):
    assert not event.logo
    response = orga_client.get(event.urls.base, follow=True)
    assert '<img "src="/media' not in response.content.decode()
    with open('../assets/icon.png', 'rb') as logo:
        response = orga_client.post(
            event.orga_urls.edit_settings,
            {
                'name_0': event.name,
                'slug': 'logotest',
                'locales': event.locales,
                'locale': event.locale,
                'date_from': event.date_from,
                'date_to': event.date_to,
                'timezone': event.timezone,
                'email': event.email,
                'primary_color': '#00ff00',
                'custom_css': '',
                'logo': logo,
            },
            follow=True,
        )
    event.refresh_from_db()
    assert event.primary_color == '#00ff00'
    assert response.status_code == 200
    assert event.logo
    response = orga_client.get(event.urls.base, follow=True)
    assert '<img src="/media' in response.content.decode(), response.content.decode()


@pytest.mark.django_db
def test_add_logo_no_svg(event, orga_client):
    assert not event.logo
    response = orga_client.get(event.urls.base, follow=True)
    assert '<img "src="/media' not in response.content.decode()
    with open('../assets/icon.svg', 'rb') as logo:
        response = orga_client.post(
            event.orga_urls.edit_settings,
            {
                'name_0': event.name,
                'slug': 'logotest',
                'locales': event.locales,
                'locale': event.locale,
                'date_from': event.date_from,
                'date_to': event.date_to,
                'timezone': event.timezone,
                'email': event.email,
                'primary_color': '#00ff00',
                'custom_css': '',
                'logo': logo,
            },
            follow=True,
        )
    event.refresh_from_db()
    assert event.primary_color != '#00ff00'
    assert response.status_code == 200
    assert not event.logo
    response = orga_client.get(event.urls.base, follow=True)
    assert '<img src="/media' not in response.content.decode(), response.content.decode()


@pytest.mark.django_db
def test_change_custom_domain(event, orga_client, monkeypatch):
    from pretalx.orga.forms.event import socket
    yessocket = lambda x: True  # noqa
    monkeypatch.setattr(socket, 'gethostbyname', yessocket)
    assert not event.settings.custom_domain
    response = orga_client.post(
        event.orga_urls.edit_settings,
        {
            'name_0': event.name,
            'slug': event.slug,
            'locales': event.locales,
            'locale': event.locale,
            'date_from': event.date_from,
            'date_to': event.date_to,
            'timezone': event.timezone,
            'email': event.email,
            'primary_color': '',
            'custom_css': '',
            'logo': '',
            'settings-custom_domain': 'https://myevent.com',
        },
        follow=True,
    )
    event = Event.objects.get(pk=event.pk)
    assert response.status_code == 200
    assert event.settings.custom_domain == 'https://myevent.com'


@pytest.mark.django_db
def test_change_custom_domain_to_site_url(event, orga_client):
    assert not event.settings.custom_domain
    response = orga_client.post(
        event.orga_urls.edit_settings,
        {
            'name_0': event.name,
            'slug': event.slug,
            'locales': event.locales,
            'locale': event.locale,
            'date_from': event.date_from,
            'date_to': event.date_to,
            'timezone': event.timezone,
            'email': event.email,
            'primary_color': '',
            'custom_css': '',
            'logo': '',
            'settings-custom_domain': settings.SITE_URL,
        },
        follow=True,
    )
    event = Event.objects.get(pk=event.pk)
    assert response.status_code == 200
    assert not event.settings.custom_domain


@pytest.mark.django_db
def test_change_custom_domain_to_other_event_domain(event, orga_client, other_event):
    other_event.settings.set('custom_domain', 'https://myevent.com')
    assert not event.settings.custom_domain
    response = orga_client.post(
        event.orga_urls.edit_settings,
        {
            'name_0': event.name,
            'slug': event.slug,
            'locales': event.locales,
            'locale': event.locale,
            'date_from': event.date_from,
            'date_to': event.date_to,
            'timezone': event.timezone,
            'email': event.email,
            'primary_color': '',
            'custom_css': '',
            'logo': '',
            'settings-custom_domain': other_event.settings.custom_domain,
        },
        follow=True,
    )
    event = Event.objects.get(pk=event.pk)
    assert response.status_code == 200
    assert not event.settings.custom_domain


@pytest.mark.django_db
def test_change_custom_domain_to_unavailable_domain(event, orga_client, other_event, monkeypatch):
    from pretalx.orga.forms.event import socket

    def nosocket(param):
        raise OSError
    monkeypatch.setattr(socket, 'gethostbyname', nosocket)
    assert not event.settings.custom_domain
    response = orga_client.post(
        event.orga_urls.edit_settings,
        {
            'name_0': event.name,
            'slug': event.slug,
            'locales': event.locales,
            'locale': event.locale,
            'date_from': event.date_from,
            'date_to': event.date_to,
            'timezone': event.timezone,
            'email': event.email,
            'primary_color': '',
            'custom_css': '',
            'logo': '',
            'settings-custom_domain': 'https://example.org',
        },
        follow=True,
    )
    event = Event.objects.get(pk=event.pk)
    assert response.status_code == 200
    assert not event.settings.custom_domain


@pytest.mark.django_db
def test_toggle_event_is_public(event, orga_client):
    assert event.is_public
    response = orga_client.get(
        event.orga_urls.live, follow=True
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.is_public
    response = orga_client.post(
        event.orga_urls.live, {'action': 'activate'}, follow=True
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.is_public
    response = orga_client.post(
        event.orga_urls.live, {'action': 'deactivate'}, follow=True
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert not event.is_public
    response = orga_client.post(
        event.orga_urls.live, {'action': 'deactivate'}, follow=True
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert not event.is_public
    response = orga_client.post(
        event.orga_urls.live, {'action': 'activate'}, follow=True
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.is_public


@pytest.mark.django_db
def test_invite_orga_member(orga_client, event):
    team = event.organiser.teams.get(can_change_submissions=True, is_reviewer=False)
    assert team.members.count() == 1
    assert team.invites.count() == 0
    response = orga_client.post(
        team.orga_urls.base,
        {'email': 'other@user.org', 'form': 'invite'},
        follow=True,
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1, response.content.decode()
    assert str(team) in str(team.invites.first())


@pytest.mark.django_db
def test_retract_invitation(orga_client, event):
    team = event.organiser.teams.get(can_change_submissions=True, is_reviewer=False)
    response = orga_client.post(
        team.orga_urls.base,
        {'email': 'other@user.org', 'form': 'invite'},
        follow=True,
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1, response.content.decode()
    invite = team.invites.first()
    response = orga_client.get(
        team.organiser.orga_urls.teams + f'{invite.id}/uninvite', follow=True
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1, response.content.decode()
    response = orga_client.post(
        team.organiser.orga_urls.teams + f'{invite.id}/uninvite', follow=True
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 0


@pytest.mark.django_db
def test_delete_team_member(orga_client, event, other_orga_user):
    team = event.organiser.teams.get(can_change_submissions=False, is_reviewer=True)
    team.members.add(other_orga_user)
    team.save()
    member = team.members.first()
    count = team.members.count()
    url = team.orga_urls.delete + f'/{member.pk}'
    assert count
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    assert team.members.count() == count
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    assert team.members.count() == count - 1


@pytest.mark.django_db
def test_reset_team_member_password(orga_client, event, other_orga_user):
    djmail.outbox = []
    team = event.organiser.teams.get(can_change_submissions=False, is_reviewer=True)
    team.members.add(other_orga_user)
    team.save()
    member = team.members.first()
    assert not member.pw_reset_token
    url = team.orga_urls.base + f'reset/{member.pk}'
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.pw_reset_token
    assert len(djmail.outbox) == 1


@pytest.mark.django_db
def test_delete_event_team(orga_client, event):
    count = event.teams.count()
    team = event.organiser.teams.get(can_change_submissions=False, is_reviewer=True)
    response = orga_client.get(team.orga_urls.delete, follow=True)
    assert response.status_code == 200
    assert event.teams.count() == count
    response = orga_client.post(team.orga_urls.delete, follow=True)
    assert response.status_code == 200
    assert event.teams.count() == count - 1


@pytest.mark.django_db
def test_activate_plugin(event, orga_client, orga_user, monkeypatch):
    plugin_name = 'plugin:tests'
    orga_user.is_administrator = True
    orga_user.save()

    assert not event.plugins
    response = orga_client.post(
        event.orga_urls.plugins, follow=True, data={plugin_name: 'enable'}
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.plugins == 'tests'
    response = orga_client.post(
        event.orga_urls.plugins, follow=True, data={plugin_name: 'disable'}
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.plugins == ''


@pytest.mark.django_db
def test_organiser_cannot_delete_event(event, orga_client, submission):
    assert Event.objects.count() == 1
    response = orga_client.post(event.orga_urls.delete, follow=True)
    assert response.status_code == 404
    assert Event.objects.count() == 1


@pytest.mark.django_db
def test_administrator_can_delete_event(event, administrator_client, submission):
    assert Event.objects.count() == 1
    response = administrator_client.get(event.orga_urls.delete, follow=True)
    assert response.status_code == 200
    response = administrator_client.post(event.orga_urls.delete, follow=True)
    assert response.status_code == 200
    assert Event.objects.count() == 0


@pytest.mark.django_db
def test_edit_review_settings(orga_client, event):
    assert event.settings.review_min_score == 0
    assert event.settings.review_max_score == 1
    assert event.settings.review_score_names is None
    assert event.review_phases.count() == 2
    response = orga_client.post(
        event.orga_urls.review_settings,
        {
            'review_min_score': '0',
            'review_max_score': '2',
            'review_score_name_0': 'OK',
            'review_score_name_1': 'Want',
            'review_score_name_2': 'Super',
            'form-TOTAL_FORMS': 2,
            'form-INITIAL_FORMS': 2,
            'form-MIN_NUM_FORMS': 0,
            'form-MAX_NUM_FORMS': 1000,
            'form-0-name': event.active_review_phase.name + 'xxx',
            'form-0-id': event.active_review_phase.id,
            'form-0-start': "",
            'form-0-end': "",
            'form-0-can_see_other_reviews': 'after_review',
            'form-1-name': event.active_review_phase.name + 'xxxy',
            'form-1-id': event.active_review_phase.id + 1,
            'form-1-start': "",
            'form-1-end': "",
            'form-1-can_see_other_reviews': 'after_review',
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    assert response.status_code == 200
    assert event.settings.review_min_score == 0
    assert event.settings.review_max_score == 2


@pytest.mark.django_db
def test_edit_review_settings_invalid(orga_client, event):
    assert event.settings.review_min_score == 0
    assert event.settings.review_max_score == 1
    assert event.settings.review_score_names is None
    response = orga_client.post(
        event.orga_urls.review_settings,
        {
            'review_min_score': '2',
            'review_max_score': '2',
            'review_score_name_0': 'OK',
            'review_score_name_1': 'Want',
            'review_score_name_2': 'Super',
            'form-TOTAL_FORMS': 2,
            'form-INITIAL_FORMS': 2,
            'form-MIN_NUM_FORMS': 0,
            'form-MAX_NUM_FORMS': 1000,
            'form-0-name': event.active_review_phase.name + 'xxx',
            'form-0-id': event.active_review_phase.id,
            'form-0-start': "",
            'form-0-end': "",
            'form-0-can_see_other_reviews': 'after_review',
            'form-1-name': event.active_review_phase.name + 'xxxy',
            'form-1-id': event.active_review_phase.id + 1,
            'form-1-start': "",
            'form-1-end': "",
            'form-1-can_see_other_reviews': 'after_review',
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    assert response.status_code == 200
    assert event.settings.review_min_score == 0
    assert event.settings.review_max_score == 1


@pytest.mark.django_db
def test_edit_review_settings_invalid_formset(orga_client, event):
    assert event.settings.review_min_score == 0
    assert event.settings.review_max_score == 1
    assert event.settings.review_score_names is None
    assert event.review_phases.count() == 2
    response = orga_client.post(
        event.orga_urls.review_settings,
        {
            'review_min_score': '0',
            'review_max_score': '2',
            'review_score_name_0': 'OK',
            'review_score_name_1': 'Want',
            'review_score_name_2': 'Super',
            'form-TOTAL_FORMS': 2,
            'form-INITIAL_FORMS': 2,
            'form-MIN_NUM_FORMS': 0,
            'form-MAX_NUM_FORMS': 1000,
            'form-0-name': event.active_review_phase.name + 'xxx',
            'form-0-id': event.active_review_phase.id,
            'form-0-start': "lalala",
            'form-0-end': "",
            'form-0-can_see_other_reviews': 'after_review',
            'form-1-name': event.active_review_phase.name + 'xxxy',
            'form-1-id': event.active_review_phase.id + 1,
            'form-1-start': "",
            'form-1-end': "",
            'form-1-can_see_other_reviews': 'after_review',
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    assert response.status_code == 200
    assert event.settings.review_max_score != 2


@pytest.mark.django_db
def test_edit_review_settings_new_review_phase(orga_client, event):
    assert event.settings.review_min_score == 0
    assert event.settings.review_max_score == 1
    assert event.settings.review_score_names is None
    assert event.review_phases.count() == 2
    response = orga_client.post(
        event.orga_urls.review_settings,
        {
            'review_min_score': '0',
            'review_max_score': '2',
            'review_score_name_0': 'OK',
            'review_score_name_1': 'Want',
            'review_score_name_2': 'Super',
            'form-TOTAL_FORMS': 3,
            'form-INITIAL_FORMS': 2,
            'form-MIN_NUM_FORMS': 0,
            'form-MAX_NUM_FORMS': 1000,
            'form-0-name': event.active_review_phase.name + 'xxx',
            'form-0-id': event.active_review_phase.id,
            'form-0-start': "",
            'form-0-end': "",
            'form-0-can_see_other_reviews': 'after_review',
            'form-1-name': event.active_review_phase.name + 'xxxy',
            'form-1-id': event.active_review_phase.id + 1,
            'form-1-start': "",
            'form-1-end': "",
            'form-1-can_see_other_reviews': 'after_review',
            'form-2-name': 'New Review Phase',
            'form-2-start': "",
            'form-2-end': "",
            'form-2-can_see_other_reviews': 'always',
        },
        follow=True,
    )
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    assert event.review_phases.count() == 3


@pytest.mark.django_db
def test_edit_review_settings_delete_review_phase(orga_client, event):
    assert event.review_phases.count() == 2
    response = orga_client.get(event.review_phases.first().urls.delete, follow=True)
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    assert event.review_phases.count() == 1


@pytest.mark.django_db
def test_edit_review_settings_activate_review_phase(orga_client, event):
    assert event.review_phases.count() == 2
    phase = event.active_review_phase
    other_phase = event.review_phases.exclude(pk=phase.pk).first()
    response = orga_client.get(other_phase.urls.activate, follow=True)
    assert response.status_code == 200
    event = Event.objects.get(slug=event.slug)
    assert event.active_review_phase == other_phase


@pytest.mark.django_db
def test_edit_review_settings_move_review_phase(orga_client, event):
    assert event.review_phases.count() == 2
    phase = event.review_phases.first()
    assert phase.position == 0
    response = orga_client.get(phase.urls.down, follow=True)
    assert response.status_code == 200
    phase.refresh_from_db()
    assert phase.position == 1
    response = orga_client.get(phase.urls.up, follow=True)
    assert response.status_code == 200
    phase.refresh_from_db()
    assert phase.position == 0


@pytest.mark.django_db
def test_organiser_can_see_event_suggestions(orga_client, event):
    response = orga_client.get('/orga/event/typeahead/')
    assert response.status_code == 200
    content = json.loads(response.content.decode())['results']
    assert len(content) == 1
    assert content[0]['id'] == event.id


@pytest.mark.django_db
def test_speaker_cannot_see_event_suggestions(speaker_client, event):
    response = speaker_client.get('/orga/event/typeahead/')
    assert response.status_code == 200
    content = json.loads(response.content.decode())['results']
    assert len(content) == 0
