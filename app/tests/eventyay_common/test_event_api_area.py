"""Tests for the dedicated event API area (#4440)."""

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import override_settings
from django.urls import resolve, reverse

from eventyay.base.models import Team
from eventyay.base.models.organizer import TeamAPIToken
from eventyay.eventyay_common.api_catalog import build_api_catalog
from eventyay.eventyay_common.navigation import get_event_navigation


def _api_url(event):
    return reverse(
        'eventyay_common:event.api',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )


def _attach_session(request):
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    return request


def test_event_navigation_includes_api(rf, event, user, team):
    path = reverse(
        'eventyay_common:event.update',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    request = _attach_session(rf.get(path))
    request.user = user
    request.event = event
    request.organizer = event.organizer
    request.resolver_match = resolve(path)

    nav = get_event_navigation(request, event)
    api_item = next(item for item in nav if str(item['label']) == 'API')
    assert api_item['url'] == _api_url(event)
    assert api_item['icon'] == 'code'


def test_api_page_requires_event_settings_permission(client, event, user):
    client.force_login(user)
    response = client.get(_api_url(event))
    assert response.status_code in (403, 302, 404)


@override_settings(SITE_URL='https://testserver')
def test_api_page_renders_for_organiser(organizer_client, event, team):
    response = organizer_client.get(_api_url(event))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'API overview' in content
    assert 'Access levels' in content
    assert 'Token management' in content
    assert 'Available endpoints' in content
    assert f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/' in content
    assert 'speakers/' in content
    assert 'submissions/' in content
    assert 'reviews/' in content


def test_api_catalog_hides_orders_without_permission(rf, event, organizer, user):
    Team.objects.create(
        organizer=organizer,
        name='Settings only',
        all_events=True,
        can_change_event_settings=True,
        can_view_orders=False,
        can_change_items=False,
    ).members.add(user)

    request = _attach_session(rf.get(_api_url(event)))
    request.user = user
    groups = build_api_catalog(request, event)
    ticket_group = next((g for g in groups if g.key == 'tickets'), None)
    if ticket_group:
        names = [str(e.name) for e in ticket_group.endpoints]
        assert 'Orders' not in names
        assert 'Products' not in names


def test_api_catalog_shows_orders_with_permission(rf, event, user, team):
    request = _attach_session(rf.get(_api_url(event)))
    request.user = user
    groups = build_api_catalog(request, event)
    ticket_group = next(g for g in groups if g.key == 'tickets')
    names = [str(e.name) for e in ticket_group.endpoints]
    assert 'Orders' in names
    assert 'Products' in names


@override_settings(SITE_URL='https://testserver')
def test_create_and_revoke_team_token_from_api_page(organizer_client, event, team):
    url = _api_url(event)
    response = organizer_client.post(
        url,
        {
            'token_action': 'create',
            'team_id': str(team.pk),
            f'token-{team.pk}-name': 'CI Token',
        },
    )
    assert response.status_code == 302
    token = TeamAPIToken.objects.get(team=team, name='CI Token', active=True)

    response = organizer_client.post(
        url,
        {
            'token_action': 'revoke',
            'team_id': str(team.pk),
            'token_id': str(token.pk),
        },
    )
    assert response.status_code == 302
    token.refresh_from_db()
    assert token.active is False


@override_settings(SITE_URL='https://testserver')
def test_token_create_denied_without_can_change_teams(client, event, organizer):
    user = get_user_model().objects.create_user(
        email='settings-only@example.com',
        password='testpass123',
    )
    Team.objects.create(
        organizer=organizer,
        name='No team mgmt',
        all_events=True,
        can_change_event_settings=True,
        can_change_teams=False,
    ).members.add(user)
    client.force_login(user)
    response = client.post(
        _api_url(event),
        {
            'token_action': 'create',
            'team_id': '1',
            'token-1-name': 'Should fail',
        },
    )
    assert response.status_code == 302
    assert not TeamAPIToken.objects.filter(name='Should fail').exists()
