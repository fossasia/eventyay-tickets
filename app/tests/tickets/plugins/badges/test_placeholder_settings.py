import datetime
import json

from django.test import override_settings
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Question, Team, User
from eventyay.base.models import Product as Item
from eventyay.plugins.badges.utils import (
    DEFAULT_BADGE_ENABLED_PLACEHOLDERS,
    get_categorized_badge_placeholders,
    get_event_allowed_badge_placeholders,
    get_placeholder_category,
)
from tests.tickets.base import SoupTest, extract_form_fields


class BadgePlaceholderUtilsTest(SoupTest):
    def setUp(self):
        super().setUp()
        with scopes_disabled():
            self.organizer = Organizer.objects.create(name='CCC', slug='ccc')
            self.event = Event.objects.create(
                organizer=self.organizer,
                name='30C3',
                slug='30c3',
                plugins='eventyay.plugins.badges',
                date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.UTC),
            )

    def test_default_allowed_placeholders_when_unset(self):
        allowed = get_event_allowed_badge_placeholders(self.event)
        assert set(allowed) == set(DEFAULT_BADGE_ENABLED_PLACEHOLDERS)
        assert 'attendee_name' in allowed
        assert 'secret' in allowed
        assert 'product' in allowed

    def test_custom_allowed_placeholders(self):
        with scopes_disabled():
            self.event.settings.badge_allowed_placeholders = json.dumps(['attendee_name', 'event_name'])
            allowed = get_event_allowed_badge_placeholders(self.event)
            assert allowed == ['attendee_name', 'event_name']

    def test_invalid_json_fallback(self):
        with scopes_disabled():
            self.event.settings.badge_allowed_placeholders = 'invalid json['
            allowed = get_event_allowed_badge_placeholders(self.event)
            assert set(allowed) == set(DEFAULT_BADGE_ENABLED_PLACEHOLDERS)

    def test_categorized_placeholders_includes_questions(self):
        with scopes_disabled():
            q = Question.objects.create(
                event=self.event,
                question='T-Shirt Size',
                type=Question.TYPE_STRING,
            )
            categories = get_categorized_badge_placeholders(self.event)
            category_ids = [cat['id'] for cat in categories]
            assert 'attendee' in category_ids
            assert 'event' in category_ids
            assert 'product_order' in category_ids
            assert 'questions' in category_ids

            questions_cat = next(cat for cat in categories if cat['id'] == 'questions')
            question_keys = [item['key'] for item in questions_cat['items']]
            assert f'question_{q.pk}' in question_keys

    def test_get_placeholder_category(self):
        assert get_placeholder_category('attendee_name') == 'attendee'
        assert get_placeholder_category('attendee_job_title') == 'attendee'
        assert get_placeholder_category('event_name') == 'event'
        assert get_placeholder_category('product') == 'product_order'
        assert get_placeholder_category('secret') == 'product_order'
        assert get_placeholder_category('invoice_name') == 'invoice'
        assert get_placeholder_category('question_123') == 'questions'
        assert get_placeholder_category('seat') == 'misc'
        assert get_placeholder_category('now_date') == 'misc'


@override_settings(SITE_URL='https://testserver')
class BadgePlaceholderControlTest(SoupTest):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        self.orga1 = Organizer.objects.create(name='CCC', slug='ccc')
        self.event1 = Event.objects.create(
            organizer=self.orga1,
            name='30C3',
            slug='30c3',
            plugins='eventyay.plugins.badges',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.UTC),
        )
        self.item1 = Item.objects.create(event=self.event1, name='Standard', default_price=0, position=1)
        t = Team.objects.create(
            organizer=self.orga1,
            can_change_event_settings=True,
            can_view_orders=True,
            can_change_items=True,
            all_events=True,
            can_create_events=True,
            can_change_orders=True,
            can_change_vouchers=True,
        )
        t.members.add(self.user)
        t.limit_events.add(self.event1)
        self.client.login(email='dummy@dummy.dummy', password='dummy')

    def test_index_toolbar_contains_settings_link(self):
        doc = self.get_doc(f'/control/event/{self.orga1.slug}/{self.event1.slug}/badges/')
        settings_links = [
            a['href'] for a in doc.select('a')
            if f'/control/event/{self.orga1.slug}/{self.event1.slug}/badges/settings' in a.get('href', '')
        ]
        assert len(settings_links) > 0

    def test_get_event_settings(self):
        doc = self.get_doc(f'/control/event/{self.orga1.slug}/{self.event1.slug}/badges/settings')
        assert doc.select('[data-placeholder-grid-widget]')
        assert doc.select('[data-placeholder-grid-select-default]')

    def test_post_event_settings(self):
        url = f'/control/event/{self.orga1.slug}/{self.event1.slug}/badges/settings'
        doc = self.get_doc(url)
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['allowed_placeholders'] = ['attendee_name', 'event_name', 'secret']
        doc = self.post_doc(url, form_data)
        assert doc.select('.alert-success')

        with scopes_disabled():
            self.event1.settings.flush()
            allowed = get_event_allowed_badge_placeholders(self.event1)
            assert set(allowed) == {'attendee_name', 'event_name', 'secret'}

    def test_editor_view_filters_variables(self):
        with scopes_disabled():
            self.event1.settings.badge_allowed_placeholders = json.dumps(['attendee_name', 'secret'])
            layout = self.event1.badge_layouts.create(name='Layout 1', default=True)

        url = f'/control/event/{self.orga1.slug}/{self.event1.slug}/badges/{layout.pk}/editor'
        response = self.client.get(url)
        assert response.status_code == 200
        variables = response.context['variables']
        assert 'attendee_name' in variables
        assert 'secret' in variables
        assert 'invoice_city' not in variables
