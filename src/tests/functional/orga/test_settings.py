import pytest

from pretalx.event.models import Event


@pytest.mark.django_db
def test_edit_mail_settings(orga_client, event, availability):
    assert event.settings.mail_from != 'foo@bar.com'
    assert event.settings.smtp_port != '25'
    response = orga_client.get(
        event.orga_urls.mail_settings,
        follow=True,
    )
    assert response.status_code == 200
    response = orga_client.post(
        event.orga_urls.mail_settings,
        follow=True,
        data={
            'mail_from': 'foo@bar.com',
            'smtp_host': 'foo.bar.com',
            'smtp_password': '',
            'smtp_port': '25',
        }
    )
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    assert event.settings.mail_from == 'foo@bar.com'
    assert event.settings.smtp_port == 25


@pytest.mark.django_db
def test_test_mail_settings(orga_client, event, availability):
    assert event.settings.mail_from != 'foo@bar.com'
    assert event.settings.smtp_port != '25'
    response = orga_client.get(
        event.orga_urls.mail_settings,
        follow=True,
    )
    assert response.status_code == 200
    response = orga_client.post(
        event.orga_urls.mail_settings,
        follow=True,
        data={
            'mail_from': 'foo@bar.com',
            'smtp_host': 'foo.bar.com',
            'smtp_password': '',
            'smtp_port': '25',
            'smtp_use_custom': '1',
            'test': '1',
        }
    )
    assert response.status_code == 200
    event = Event.objects.get(pk=event.pk)
    assert event.settings.mail_from == 'foo@bar.com'
    assert event.settings.smtp_port == 25


@pytest.mark.django_db
@pytest.mark.parametrize('path,allowed', (
    ('tests/functional/orga/fixtures/custom.css', True),
    ('tests/functional/orga/fixtures/malicious.css', False),
    ('tests/conftest.py', False),
))
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
                'is_public': event.is_public,
                'date_from': event.date_from,
                'date_to': event.date_to,
                'timezone': event.timezone,
                'email': event.email,
                'primary_color': event.primary_color,
                'custom_css': custom_css
            },
            follow=True
        )
    event.refresh_from_db()
    assert response.status_code == 200
    assert bool(event.custom_css) == allowed


@pytest.mark.django_db
def test_add_logo(event, orga_client):
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
                'is_public': event.is_public,
                'date_from': event.date_from,
                'date_to': event.date_to,
                'timezone': event.timezone,
                'email': event.email,
                'primary_color': '#00ff00',
                'custom_css': None,
                'logo': logo,
            },
            follow=True
        )
    event.refresh_from_db()
    assert event.slug != 'logotest'
    assert event.primary_color == '#00ff00'
    assert response.status_code == 200
    assert event.logo
    response = orga_client.get(event.urls.base, follow=True)
    assert '<img src="/media' in response.content.decode(), response.content.decode()


@pytest.mark.django_db
def test_invite_orga_member(orga_client, event):
    team = event.organiser.teams.get(can_change_submissions=True, is_reviewer=False)
    assert team.members.count() == 1
    assert team.invites.count() == 0
    response = orga_client.post(
        event.orga_urls.team_settings + f'/{team.id}',
        {
            'email': 'other@user.org',
            'form': 'invite',
        }, follow=True,
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1
    assert str(team) in str(team.invites.first())


@pytest.mark.django_db
def test_retract_invitation(orga_client, event):
    team = event.organiser.teams.get(can_change_submissions=True, is_reviewer=False)
    response = orga_client.post(
        event.orga_urls.team_settings + f'/{team.id}',
        {
            'email': 'other@user.org',
            'form': 'invite',
        }, follow=True,
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1
    invite = team.invites.first()
    response = orga_client.get(
        event.orga_urls.team_settings + f'/{invite.id}/uninvite',
        follow=True,
    )
    assert response.status_code == 200
    assert team.members.count() == 1
    assert team.invites.count() == 1
    response = orga_client.post(
        event.orga_urls.team_settings + f'/{invite.id}/uninvite',
        follow=True,
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
    url = event.orga_urls.team_settings + f'/{team.pk}/delete/{member.pk}'
    assert count
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    assert team.members.count() == count
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    assert team.members.count() == count - 1


@pytest.mark.django_db
def test_delete_event_team(orga_client, event):
    count = event.teams.count()
    team = event.organiser.teams.get(can_change_submissions=False, is_reviewer=True)
    url = event.orga_urls.team_settings + f'/{team.pk}/delete'
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    assert event.teams.count() == count
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    assert event.teams.count() == count - 1


@pytest.mark.django_db
def test_activate_plugin(event, orga_client, orga_user, monkeypatch):
    class Plugin:
        module = name = 'test_plugin'
        visible = True
        app = None

    monkeypatch.setattr('pretalx.common.plugins.get_all_plugins', lambda: [Plugin()])
    plugin_name = 'plugin:test_plugin'
    orga_user.is_administrator = True
    orga_user.save()

    assert not event.plugins
    response = orga_client.post(
        event.orga_urls.plugins, follow=True,
        data={plugin_name: 'enable'},
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.plugins == 'test_plugin'
    response = orga_client.post(
        event.orga_urls.plugins, follow=True,
        data={plugin_name: 'disable'},
    )
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.plugins == ''
