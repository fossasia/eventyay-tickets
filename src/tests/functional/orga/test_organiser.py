import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_orga_edit_organiser(orga_client, organiser):
    response = orga_client.post(
        organiser.orga_urls.base + '/',
        data={
            'name_0': 'The bestest organiser',
            'name_1': 'The bestest organiser',
        },
        follow=True,
    )
    organiser.refresh_from_db()
    assert response.status_code == 200, response.content.decode()
    assert str(organiser.name) == 'The bestest organiser', response.content.decode()
    assert str(organiser) == str(organiser.name)


@pytest.mark.django_db
def test_orga_edit_team(orga_client, organiser, event):
    team = organiser.teams.first()
    url = reverse('orga:organiser.teams.view', kwargs={'organiser': organiser.slug, 'pk': team.pk})
    response = orga_client.get(url, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        url, follow=True,
        data={
            'all_events': True,
            'can_change_submissions': True,
            'can_change_organiser_settings': True,
            'can_change_event_settings': True,
            'can_change_teams': True,
            'can_create_events': True,
            'form': 'team',
            'limit_events': event.pk,
            'name': 'Fancy New Name',
        },
    )
    assert response.status_code == 200
    team.refresh_from_db()
    assert team.name == 'Fancy New Name'


@pytest.mark.django_db
def test_orga_create_team(orga_client, organiser, event):
    count = organiser.teams.count()
    response = orga_client.get(organiser.orga_urls.new_team, follow=True)
    assert response.status_code == 200
    response = orga_client.post(
        organiser.orga_urls.new_team, follow=True,
        data={
            'all_events': True,
            'can_change_submissions': True,
            'can_change_organiser_settings': True,
            'can_change_event_settings': True,
            'can_change_teams': True,
            'can_create_events': True,
            'form': 'team',
            'limit_events': event.pk,
            'name': 'Fancy New Name',
            'organiser': organiser.pk,
        },
    )
    assert response.status_code == 200
    assert organiser.teams.count() == count + 1, response.content.decode()
