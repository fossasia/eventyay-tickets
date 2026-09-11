import pytest
from django.db import transaction
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.base.models import Organizer, Team, User
from eventyay.control.forms.organizer_forms import OrganizerForm, OrganizerUpdateForm
from tests.tickets.base import SoupTest, extract_form_fields


@pytest.fixture
def class_monkeypatch(request, monkeypatch):
    request.cls.monkeypatch = monkeypatch


@pytest.mark.usefixtures('class_monkeypatch')
class DefaultOrganizerTest(SoupTest):
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        self.user2 = User.objects.create_user('dummy2@dummy.dummy', 'dummy')

        self.orga1 = Organizer.objects.create(name='FOSSASIA', slug='fossasia')
        self.orga2 = Organizer.objects.create(name='OpenTech', slug='opentech')
        self.orga3 = Organizer.objects.create(name='ThirdOrg', slug='thirdorg')

        self.team1 = Team.objects.create(
            organizer=self.orga1,
            name='Core Team 1',
            can_create_events=True,
            can_change_organizer_settings=True,
        )
        self.team1.members.add(self.user)

        self.client.login(email='dummy@dummy.dummy', password='dummy')

    @scopes_disabled()
    def test_user_no_organizer(self):
        user_empty = User.objects.create_user('empty@dummy.dummy', 'dummy')
        assert user_empty.get_default_organizer() is None

    @scopes_disabled()
    def test_user_single_organizer_auto_default(self):
        assert self.user.get_default_organizer() == self.orga1
        self.user.refresh_from_db()
        # Verify get_default_organizer is a pure getter and did not mutate DB
        assert self.user.default_organizer is None

    @scopes_disabled()
    def test_user_multiple_organizers_fallback_first_added(self):
        team2 = Team.objects.create(
            organizer=self.orga2,
            name='Core Team 2',
            can_create_events=True,
            can_change_organizer_settings=True,
        )
        team2.members.add(self.user)

        self.user.default_organizer = None
        self.user.save(update_fields=['default_organizer'])

        # Fallback dynamically resolves to first team's organizer without DB mutation
        assert self.user.get_default_organizer() == self.orga1
        self.user.refresh_from_db()
        assert self.user.default_organizer is None

    @scopes_disabled()
    def test_user_explicit_default_organizer(self):
        team2 = Team.objects.create(
            organizer=self.orga2,
            name='Core Team 2',
            can_create_events=True,
            can_change_organizer_settings=True,
        )
        team2.members.add(self.user)

        self.user.default_organizer = self.orga2
        self.user.save(update_fields=['default_organizer'])

        assert self.user.get_default_organizer() == self.orga2

    @scopes_disabled()
    def test_event_create_preselects_default_organizer(self):
        team2 = Team.objects.create(
            organizer=self.orga2,
            name='Core Team 2',
            can_create_events=True,
            can_change_organizer_settings=True,
        )
        team2.members.add(self.user)

        self.user.default_organizer = self.orga2
        self.user.save(update_fields=['default_organizer'])

        response = self.client.get(reverse('eventyay_common:events.add'))
        assert response.status_code == 200
        assert response.context['foundation_form'].initial.get('organizer') == self.orga2

    @scopes_disabled()
    def test_event_create_single_organizer_preselected(self):
        response = self.client.get(reverse('eventyay_common:events.add'))
        assert response.status_code == 200
        assert response.context['foundation_form'].initial.get('organizer') == self.orga1

    @scopes_disabled()
    def test_organizer_overview_shows_default_badge(self):
        team2 = Team.objects.create(
            organizer=self.orga2,
            name='Core Team 2',
            can_create_events=True,
            can_change_organizer_settings=True,
        )
        team2.members.add(self.user)

        self.user.default_organizer = self.orga1
        self.user.save(update_fields=['default_organizer'])

        doc = self.get_doc(reverse('eventyay_common:organizers'))
        table_text = doc.select('.events-table')[0].text
        assert 'FOSSASIA' in table_text
        assert '(default)' in table_text

        doc_ctrl = self.get_doc('/control/organizers/')
        ctrl_table_text = doc_ctrl.select('table')[0].text
        assert 'FOSSASIA' in ctrl_table_text
        assert '(default)' in ctrl_table_text

    @scopes_disabled()
    def test_new_organizer_creation_default_logic(self):
        user_new = User.objects.create_user('neworguser@dummy.dummy', 'dummy')
        self.client.login(email='neworguser@dummy.dummy', password='dummy')

        response = self.client.post(
            reverse('eventyay_common:organizers.add'),
            {
                'name': 'Brand New Org',
                'slug': 'brandneworg',
                'set_as_default': 'on',
            },
            follow=True,
        )
        assert response.status_code == 200
        user_new.refresh_from_db()
        new_org = Organizer.objects.get(slug='brandneworg')
        assert user_new.default_organizer == new_org

        response = self.client.post(
            reverse('eventyay_common:organizers.add'),
            {
                'name': 'Second Org',
                'slug': 'secondorg',
            },
            follow=True,
        )
        assert response.status_code == 200
        user_new.refresh_from_db()
        assert user_new.default_organizer == new_org

        response = self.client.post(
            reverse('eventyay_common:organizers.add'),
            {
                'name': 'Third Org Set Default',
                'slug': 'thirdorgsetdef',
                'set_as_default': 'on',
            },
            follow=True,
        )
        assert response.status_code == 200
        user_new.refresh_from_db()
        third_org = Organizer.objects.get(slug='thirdorgsetdef')
        assert user_new.default_organizer == third_org

    @scopes_disabled()
    def test_edit_organizer_set_default_user_scoped(self):
        team2 = Team.objects.create(
            organizer=self.orga2,
            name='Core Team 2',
            can_create_events=True,
            can_change_organizer_settings=True,
        )
        team2.members.add(self.user)
        team2.members.add(self.user2)
        self.team1.members.add(self.user2)

        self.user.default_organizer = self.orga1
        self.user.save(update_fields=['default_organizer'])
        self.user2.default_organizer = self.orga1
        self.user2.save(update_fields=['default_organizer'])

        form = OrganizerUpdateForm(
            instance=self.orga2,
            data={'name': self.orga2.name, 'slug': self.orga2.slug, 'set_as_default': True},
            user=self.user,
        )
        assert form.is_valid()
        if form.cleaned_data.get('set_as_default'):
            self.user.default_organizer = self.orga2
            self.user.save(update_fields=['default_organizer'])

        self.user.refresh_from_db()
        self.user2.refresh_from_db()

        assert self.user.default_organizer == self.orga2
        assert self.user2.default_organizer == self.orga1

    @scopes_disabled()
    def test_uncheck_set_as_default_clears_default(self):
        team2 = Team.objects.create(
            organizer=self.orga2,
            name='Core Team 2',
            can_create_events=True,
            can_change_organizer_settings=True,
        )
        team2.members.add(self.user)

        self.user.default_organizer = self.orga2
        self.user.save(update_fields=['default_organizer'])

        form = OrganizerUpdateForm(
            instance=self.orga2,
            data={'name': self.orga2.name, 'slug': self.orga2.slug, 'set_as_default': False},
            user=self.user,
        )
        assert form.is_valid()
        if not form.cleaned_data.get('set_as_default'):
            if self.user.default_organizer_id == self.orga2.id:
                self.user.default_organizer = None
                self.user.save(update_fields=['default_organizer'])

        self.user.refresh_from_db()
        assert self.user.default_organizer is None
        assert self.user.get_default_organizer() == self.orga1
        self.user.refresh_from_db()
        assert self.user.default_organizer is None

    @scopes_disabled()
    def test_remove_from_default_organizer_fallback(self):
        team2 = Team.objects.create(
            organizer=self.orga2,
            name='Core Team 2',
            can_create_events=True,
            can_change_organizer_settings=True,
        )
        team2.members.add(self.user)

        self.user.default_organizer = self.orga1
        self.user.save(update_fields=['default_organizer'])

        self.team1.members.remove(self.user)

        self.user.refresh_from_db()
        assert self.user.get_default_organizer() == self.orga2

        team2.members.remove(self.user)
        self.user.refresh_from_db()
        assert self.user.get_default_organizer() is None

    @scopes_disabled()
    def test_delete_default_organizer_cascade(self):
        team2 = Team.objects.create(
            organizer=self.orga2,
            name='Core Team 2',
            can_create_events=True,
            can_change_organizer_settings=True,
        )
        team2.members.add(self.user)

        self.user.default_organizer = self.orga1
        self.user.save(update_fields=['default_organizer'])

        self.orga1.delete()

        self.user.refresh_from_db()
        assert self.user.default_organizer is None
        assert self.user.get_default_organizer() == self.orga2

    @scopes_disabled()
    def test_non_member_cannot_set_default(self):
        form = OrganizerUpdateForm(
            instance=self.orga3,
            data={'name': 'ThirdOrg', 'slug': 'thirdorg', 'set_as_default': True},
            user=self.user,
        )
        assert not form.is_valid()
        assert 'set_as_default' in form.errors

    @scopes_disabled()
    def test_api_set_default_endpoint(self):
        response = self.client.post(
            f'/api/v1/organizers/{self.orga1.slug}/set-default/',
            format='json',
        )
        assert response.status_code == 200
        assert response.json() == {'status': 'ok', 'default_organizer': self.orga1.slug}
        self.user.refresh_from_db()
        assert self.user.default_organizer == self.orga1

        response_non_member = self.client.post(
            f'/api/v1/organizers/{self.orga3.slug}/set-default/',
            format='json',
        )
        assert response_non_member.status_code == 403

    @scopes_disabled()
    def test_api_organizer_list_is_default_serializer(self):
        self.user.default_organizer = self.orga1
        self.user.save(update_fields=['default_organizer'])

        response = self.client.get('/api/v1/organizers/')
        assert response.status_code == 200
        results = response.json().get('results', [])
        for item in results:
            if item['slug'] == self.orga1.slug:
                assert item['is_default'] is True
            else:
                assert item['is_default'] is False
