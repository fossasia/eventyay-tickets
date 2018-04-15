from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import now

from pretalx.event.models import Event


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


@pytest.mark.django_db
@pytest.mark.parametrize('deadline', (True, False))
class TestEventCreation:
    url = '/orga/event/new/'

    def post(self, step, data):
        data = {f'{step}-{key}': value for key, value in data.items()}
        data['event_wizard-current_step'] = step
        response = self.client.post(self.url, data=data, follow=True)
        assert response.status_code == 200
        return response

    def submit_initial(self, organiser):
        return self.post(step='initial', data={'locales': 'en', 'organiser': organiser.pk})

    def submit_basics(self):
        return self.post(step='basics', data={
            'email': 'foo@bar.com',
            'locale': 'en',
            'name_0': 'New event!',
            'slug': 'newevent',
            'timezone': 'Europe/Amsterdam',
        })

    def submit_timeline(self, deadline):
        _now = now()
        tomorrow = _now + timedelta(days=1)
        date = '%Y-%m-%d'
        datetime = '%Y-%m-%d %H:%M:%S'
        return self.post(step='timeline', data={'date_from': _now.strftime(date), 'date_to': tomorrow.strftime(date), 'deadline': _now.strftime(datetime) if deadline else ''})

    def submit_display(self):
        return self.post(step='display', data={'header_pattern': '', 'logo': '', 'primary_color': ''})

    def submit_copy(self, copy=False):
        return self.post(step='copy', data={'copy_from_event': copy if copy else ''})

    def test_orga_create_event(self, orga_client, organiser, deadline):
        organiser.teams.all().update(can_create_events=True)
        self.client = orga_client
        count = Event.objects.count()
        team_count = organiser.teams.count()
        self.submit_initial(organiser)
        self.submit_basics()
        self.submit_timeline(deadline=deadline)
        self.submit_display()
        self.submit_copy()
        assert Event.objects.count() == count + 1
        assert organiser.teams.count() == team_count + 1

    def test_orga_create_event_with_copy(self, orga_client, organiser, event, deadline):
        self.client = orga_client
        organiser.teams.all().update(can_create_events=True)
        count = Event.objects.count()
        team_count = organiser.teams.count()
        self.submit_initial(organiser)
        self.submit_basics()
        self.submit_timeline(deadline=deadline)
        self.submit_display()
        self.submit_copy(copy=event.pk)
        assert Event.objects.count() == count + 1
        assert organiser.teams.count() == team_count + 1

    def test_orga_create_event_no_new_team(self, orga_client, organiser, event, deadline):
        self.client = orga_client
        organiser.teams.update(all_events=True, can_create_events=True)
        count = Event.objects.count()
        team_count = organiser.teams.count()
        self.submit_initial(organiser)
        self.submit_basics()
        self.submit_timeline(deadline=deadline)
        self.submit_display()
        self.submit_copy()
        assert Event.objects.count() == count + 1
        assert organiser.teams.count() == team_count
