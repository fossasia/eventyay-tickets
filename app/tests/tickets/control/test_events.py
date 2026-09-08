import datetime
import json
import time
from decimal import Decimal

from zoneinfo import ZoneInfo
from django.utils.timezone import now
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString


from django.test import override_settings

from eventyay.base.models import Event, Order, Organizer, Team, User
from eventyay.base.models.organizer import OrganizerBillingModel
from tests.testutils.mock import mocker_context
from tests.tickets.base import SoupTest, extract_form_fields


@override_settings(SITE_URL='https://testserver')
class EventsTest(SoupTest):
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        self.orga1 = Organizer.objects.create(name='CCC', slug='ccc')
        self.orga2 = Organizer.objects.create(name='MRM', slug='mrm')
        self.orgabilling1 = OrganizerBillingModel.objects.create(
            organizer=self.orga1,
            primary_contact_name='John Doe',
            primary_contact_email='joindeo@eventyay.com',
            company_or_organization_name='Eventyay',
            address_line_1='123 Main Street',
            city='San Francisco',
            zip_code='94105',
            country='US',
            preferred_language='en',
            tax_id='123456789',
            stripe_customer_id='cus_123456789',
            stripe_payment_method_id='pm_123456789',
            stripe_setup_intent_id='seti_123456789',
        )
        self.event1 = Event.objects.create(
            organizer=self.orga1,
            name='30C3',
            slug='30c3',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
            plugins='eventyay.plugins.banktransfer,tests.tickets.testdummy',
        )
        self.event2 = Event.objects.create(
            organizer=self.orga1,
            name='31C3',
            slug='31c3',
            date_from=datetime.datetime(2014, 12, 26, tzinfo=datetime.timezone.utc),
        )
        self.event3 = Event.objects.create(
            organizer=self.orga2,
            name='MRMCD14',
            slug='mrmcd14',
            date_from=datetime.datetime(2014, 9, 5, tzinfo=datetime.timezone.utc),
        )

        self.team1 = Team.objects.create(
            organizer=self.orga1,
            can_create_events=True,
            can_change_event_settings=True,
            can_change_items=True,
        )
        self.team1.members.add(self.user)
        self.team1.limit_events.add(self.event1)

        self.team2 = Team.objects.create(
            organizer=self.orga1,
            can_change_event_settings=True,
            can_change_items=True,
            can_change_orders=True,
            can_change_vouchers=True,
        )
        self.team2.members.add(self.user)

        self.client.login(email='dummy@dummy.dummy', password='dummy')

    def test_event_list(self):
        doc = self.get_doc('/control/events/')
        tabletext = doc.select('#page-wrapper .table')[0].text
        self.assertIn('30C3', tabletext)
        self.assertNotIn('31C3', tabletext)
        self.assertNotIn('MRMCD14', tabletext)

    def test_convenience_organizer_redirect(self):
        resp = self.client.get('/control/event/%s/' % (self.orga1.slug))
        self.assertRedirects(resp, '/control/organizer/%s/' % (self.orga1.slug))

    def test_quick_setup_later(self):
        with scopes_disabled():
            self.event1.quotas.create(name='foo', size=2)
        resp = self.client.get('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        self.assertRedirects(resp, '/control/event/%s/%s/' % (self.orga1.slug, self.event1.slug))

    def test_quick_setup_total_quota(self):
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        doc.select('[name=show_quota_left]')[0]['checked'] = 'checked'
        doc.select('[name=ticket_download]')[0]['checked'] = 'checked'
        doc.select('[name=payment_banktransfer__enabled]')[0]['checked'] = 'checked'
        doc.select('[name=payment_banktransfer_bank_details_type]')[1]['checked'] = 'checked'
        del doc.select('[name=payment_banktransfer_bank_details_type]')[0]['checked']
        doc.select('[name*=payment_banktransfer_bank_details_0]')[0].contents[0].replace_with('Foo')
        doc.select('[name=total_quota]')[0]['value'] = '300'
        doc.select('[name=form-TOTAL_FORMS]')[0]['value'] = '2'
        doc.select('[name=form-INITIAL_FORMS]')[0]['value'] = '2'
        doc.select('[name=form-MIN_NUM_FORMS]')[0]['value'] = '0'
        doc.select('[name=form-MAX_NUM_FORMS]')[0]['value'] = '1000'
        doc.select('[name=form-0-name_0]')[0]['value'] = 'Normal ticket'
        doc.select('[name=form-0-default_price]')[0]['value'] = '13.90'
        doc.select('[name=form-0-quota]')[0]['value'] = ''
        doc.select('[name=form-1-name_0]')[0]['value'] = 'Reduced ticket'
        doc.select('[name=form-1-default_price]')[0]['value'] = '13.20'
        doc.select('[name=form-1-quota]')[0]['value'] = ''

        doc = self.post_doc(
            '/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug),
            extract_form_fields(doc.select('.container-fluid form')[0]),
        )
        assert len(doc.select('.alert-success')) > 0
        self.event1.refresh_from_db()
        self.event1.settings.flush()
        assert self.event1.settings.show_quota_left
        assert self.event1.settings.ticket_download
        assert self.event1.settings.ticketoutput_pdf__enabled
        assert self.event1.settings.payment_banktransfer__enabled
        assert (
            self.event1.settings.get('payment_banktransfer_bank_details', as_type=LazyI18nString).localize('en')
            == 'Foo'
        )
        assert 'eventyay.plugins.banktransfer' in self.event1.plugins
        with scopes_disabled():
            assert self.event1.products.count() == 2
            i = self.event1.products.first()
            assert str(i.name) == 'Normal ticket'
            assert i.default_price == Decimal('13.90')
            i = self.event1.products.last()
            assert str(i.name) == 'Reduced ticket'
            assert i.default_price == Decimal('13.20')
            assert self.event1.quotas.count() == 1
            q = self.event1.quotas.first()
            assert q.name == 'Tickets'
            assert q.size == 300
            assert q.products.count() == 2

    def test_quick_setup_defaults_available_until(self):
        self.event1.date_to = datetime.datetime(2013, 12, 28, 18, 0, tzinfo=datetime.timezone.utc)
        self.event1.save()
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        doc.select('[name=form-TOTAL_FORMS]')[0]['value'] = '1'
        doc.select('[name=form-INITIAL_FORMS]')[0]['value'] = '1'
        doc.select('[name=form-MIN_NUM_FORMS]')[0]['value'] = '0'
        doc.select('[name=form-MAX_NUM_FORMS]')[0]['value'] = '1000'
        doc.select('[name=form-0-name_0]')[0]['value'] = 'Normal ticket'
        doc.select('[name=form-0-default_price]')[0]['value'] = '13.90'
        doc.select('[name=form-0-quota]')[0]['value'] = '100'

        fields = extract_form_fields(doc.select('.container-fluid form')[0])
        fields['action'] = 'continue'
        fields['payment_manualpayment__enabled'] = 'on'
        doc = self.post_doc(
            '/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug),
            fields,
        )
        assert len(doc.select('.alert-success')) > 0
        with scopes_disabled():
            product = self.event1.products.get()
            assert product.available_until == self.event1.date_to

    def test_quick_setup_single_quota(self):
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        doc.select('[name=show_quota_left]')[0]['checked'] = 'checked'
        doc.select('[name=ticket_download]')[0]['checked'] = 'checked'
        doc.select('[name=payment_banktransfer__enabled]')[0]['checked'] = 'checked'
        doc.select('[name=payment_banktransfer_bank_details_type]')[1]['checked'] = 'checked'
        del doc.select('[name=payment_banktransfer_bank_details_type]')[0]['checked']
        doc.select('[name*=payment_banktransfer_bank_details_0]')[0].contents[0].replace_with('Foo')
        doc.select('[name=total_quota]')[0]['value'] = ''
        doc.select('[name=form-TOTAL_FORMS]')[0]['value'] = '2'
        doc.select('[name=form-INITIAL_FORMS]')[0]['value'] = '2'
        doc.select('[name=form-MIN_NUM_FORMS]')[0]['value'] = '0'
        doc.select('[name=form-MAX_NUM_FORMS]')[0]['value'] = '1000'
        doc.select('[name=form-0-name_0]')[0]['value'] = 'Normal ticket'
        doc.select('[name=form-0-default_price]')[0]['value'] = '13.90'
        doc.select('[name=form-0-quota]')[0]['value'] = '100'
        doc.select('[name=form-1-name_0]')[0]['value'] = 'Reduced ticket'
        doc.select('[name=form-1-default_price]')[0]['value'] = '13.20'
        doc.select('[name=form-1-quota]')[0]['value'] = '50'

        doc = self.post_doc(
            '/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug),
            extract_form_fields(doc.select('.container-fluid form')[0]),
        )
        assert len(doc.select('.alert-success')) > 0
        self.event1.refresh_from_db()
        self.event1.settings.flush()
        assert self.event1.settings.show_quota_left
        assert self.event1.settings.ticket_download
        assert self.event1.settings.ticketoutput_pdf__enabled
        assert self.event1.settings.payment_banktransfer__enabled
        assert (
            self.event1.settings.get('payment_banktransfer_bank_details', as_type=LazyI18nString).localize('en')
            == 'Foo'
        )
        assert 'eventyay.plugins.banktransfer' in self.event1.plugins
        with scopes_disabled():
            assert self.event1.products.count() == 2
            i = self.event1.products.first()
            assert str(i.name) == 'Normal ticket'
            assert i.default_price == Decimal('13.90')
            i = self.event1.products.last()
            assert str(i.name) == 'Reduced ticket'
            assert i.default_price == Decimal('13.20')
            assert self.event1.quotas.count() == 2
            q = self.event1.quotas.first()
            assert q.name == 'Normal ticket'
            assert q.size == 100
            assert q.products.count() == 1
            q = self.event1.quotas.last()
            assert q.name == 'Reduced ticket'
            assert q.size == 50
            assert q.products.count() == 1

    def test_quick_setup_dual_quota(self):
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        doc.select('[name=show_quota_left]')[0]['checked'] = 'checked'
        doc.select('[name=ticket_download]')[0]['checked'] = 'checked'
        doc.select('[name=payment_banktransfer__enabled]')[0]['checked'] = 'checked'
        doc.select('[name=payment_banktransfer_bank_details_type]')[1]['checked'] = 'checked'
        del doc.select('[name=payment_banktransfer_bank_details_type]')[0]['checked']
        doc.select('[name*=payment_banktransfer_bank_details_0]')[0].contents[0].replace_with('Foo')
        doc.select('[name=total_quota]')[0]['value'] = '120'
        doc.select('[name=form-TOTAL_FORMS]')[0]['value'] = '2'
        doc.select('[name=form-INITIAL_FORMS]')[0]['value'] = '2'
        doc.select('[name=form-MIN_NUM_FORMS]')[0]['value'] = '0'
        doc.select('[name=form-MAX_NUM_FORMS]')[0]['value'] = '1000'
        doc.select('[name=form-0-name_0]')[0]['value'] = 'Normal ticket'
        doc.select('[name=form-0-default_price]')[0]['value'] = '13.90'
        doc.select('[name=form-0-quota]')[0]['value'] = '100'
        doc.select('[name=form-1-name_0]')[0]['value'] = 'Reduced ticket'
        doc.select('[name=form-1-default_price]')[0]['value'] = '13.20'
        doc.select('[name=form-1-quota]')[0]['value'] = '50'

        doc = self.post_doc(
            '/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug),
            extract_form_fields(doc.select('.container-fluid form')[0]),
        )
        assert len(doc.select('.alert-success')) > 0
        self.event1.refresh_from_db()
        self.event1.settings.flush()
        assert self.event1.settings.show_quota_left
        assert self.event1.settings.ticket_download
        assert self.event1.settings.ticketoutput_pdf__enabled
        assert self.event1.settings.payment_banktransfer__enabled
        assert (
            self.event1.settings.get('payment_banktransfer_bank_details', as_type=LazyI18nString).localize('en')
            == 'Foo'
        )
        assert 'eventyay.plugins.banktransfer' in self.event1.plugins
        with scopes_disabled():
            assert self.event1.products.count() == 2
            i = self.event1.products.first()
            assert str(i.name) == 'Normal ticket'
            assert i.default_price == Decimal('13.90')
            i = self.event1.products.last()
            assert str(i.name) == 'Reduced ticket'
            assert i.default_price == Decimal('13.20')
            assert self.event1.quotas.count() == 3
            q = self.event1.quotas.first()
            assert q.name == 'Normal ticket'
            assert q.size == 100
            assert q.products.count() == 1
            q = self.event1.quotas.last()
            assert q.name == 'Tickets'
            assert q.size == 120
            assert q.products.count() == 2

    def test_quick_setup_wizard_elements(self):
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        # Verify quicksetup.css stylesheet is included
        assert any('quicksetup.css' in link.get('href', '') for link in doc.select('link[rel=stylesheet]'))
        # Verify 6 stepper steps exist
        steps = doc.select('.quickstart-step-item')
        assert len(steps) == 6
        # Verify Skip quickstart link exists and links to products
        skip_btn = doc.select('.quickstart-header .btn-skip')[0]
        assert 'products' in skip_btn['href']
        # Verify numbered cards exist
        cards = doc.select('.quickstart-card')
        assert len(cards) >= 6
        # Verify review summary card elements and status box exist
        assert doc.select('#step-review')
        assert doc.select('#review-status-box')
        assert doc.select('#review-currency')
        assert doc.select('#review-ticket-types')
        assert doc.select('#review-total-capacity')
        assert doc.select('#btn-edit-setup')
        # Verify checkout access field
        assert doc.select('#id_require_registered_account_for_tickets')
        # Verify Save draft and Save and continue buttons exist
        assert doc.select('.btn-save-draft')
        assert doc.select('.btn-save-continue')

    def test_quick_setup_save_continue_navigation(self):
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        fields = extract_form_fields(doc.select('.container-fluid form')[0])
        fields['action'] = 'continue'
        fields['form-TOTAL_FORMS'] = '1'
        fields['form-INITIAL_FORMS'] = '1'
        fields['form-MIN_NUM_FORMS'] = '0'
        fields['form-MAX_NUM_FORMS'] = '1000'
        fields['form-0-name_0'] = 'Standard Ticket'
        fields['form-0-default_price'] = '20.00'
        fields['form-0-quota'] = '100'
        fields['payment_manualpayment__enabled'] = 'on'

        response = self.client.post(
            '/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug),
            fields,
            follow=False,
        )
        assert response.status_code == 302
        assert response['Location'] == '/control/event/%s/%s/live/' % (self.orga1.slug, self.event1.slug)

    def test_quick_setup_save_draft_navigation(self):
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        fields = extract_form_fields(doc.select('.container-fluid form')[0])
        fields['action'] = 'draft'
        fields['form-TOTAL_FORMS'] = '1'
        fields['form-INITIAL_FORMS'] = '1'
        fields['form-MIN_NUM_FORMS'] = '0'
        fields['form-MAX_NUM_FORMS'] = '1000'
        fields['form-0-name_0'] = 'Draft ticket'
        fields['form-0-default_price'] = '0.00'
        fields['form-0-quota'] = '50'

        response = self.client.post(
            '/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug),
            fields,
            follow=False,
        )
        assert response.status_code == 302
        assert response['Location'] == '/control/event/%s/%s/' % (self.orga1.slug, self.event1.slug)
        with scopes_disabled():
            assert self.event1.products.count() == 0
        assert self.event1.settings.get('quickstart_draft') is not None

    def test_quick_setup_save_draft_bypasses_optional_sections(self):
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        fields = extract_form_fields(doc.select('.container-fluid form')[0])
        fields['action'] = 'draft'
        # Paid ticket exists but NO payment method enabled; Bank transfer checked but NO bank details
        fields['payment_banktransfer__enabled'] = 'on'
        fields.pop('payment_banktransfer_bank_details_0', None)
        fields.pop('payment_banktransfer_bank_details_type', None)
        fields['form-TOTAL_FORMS'] = '1'
        fields['form-INITIAL_FORMS'] = '1'
        fields['form-MIN_NUM_FORMS'] = '0'
        fields['form-MAX_NUM_FORMS'] = '1000'
        fields['form-0-name_0'] = 'Draft Paid Ticket'
        fields['form-0-default_price'] = '25.00'
        fields['form-0-quota'] = '50'

        doc = self.post_doc(
            '/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug),
            fields,
        )
        assert len(doc.select('.alert-success')) > 0
        assert any('draft' in alert.text.lower() for alert in doc.select('.alert-success'))
        self.event1.refresh_from_db()
        with scopes_disabled():
            assert self.event1.products.count() == 0
        draft_data = json.loads(self.event1.settings.get('quickstart_draft'))
        assert len(draft_data['tickets']) == 1
        assert draft_data['tickets'][0]['name'] == 'Draft Paid Ticket'

    def test_quick_setup_save_continue_requires_bank_details(self):
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        fields = extract_form_fields(doc.select('.container-fluid form')[0])
        fields['action'] = 'continue'
        fields['payment_banktransfer__enabled'] = 'on'
        # Missing bank details should cause validation error on continue
        fields.pop('payment_banktransfer_bank_details_0', None)
        fields.pop('payment_banktransfer_bank_details_type', None)
        fields['form-TOTAL_FORMS'] = '1'
        fields['form-INITIAL_FORMS'] = '1'
        fields['form-MIN_NUM_FORMS'] = '0'
        fields['form-MAX_NUM_FORMS'] = '1000'
        fields['form-0-name_0'] = 'Standard Ticket'
        fields['form-0-default_price'] = '25.00'
        fields['form-0-quota'] = '50'

        response = self.client.post(
            '/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug),
            fields,
            follow=False,
        )
        assert response.status_code == 200
        self.event1.refresh_from_db()
        with scopes_disabled():
            assert self.event1.products.count() == 0

    def test_quick_setup_save_continue_requires_at_least_one_named_ticket(self):
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        fields = extract_form_fields(doc.select('.container-fluid form')[0])
        fields['action'] = 'continue'
        fields['form-TOTAL_FORMS'] = '1'
        fields['form-INITIAL_FORMS'] = '1'
        fields['form-MIN_NUM_FORMS'] = '0'
        fields['form-MAX_NUM_FORMS'] = '1000'
        fields['form-0-DELETE'] = 'on'
        fields['form-0-name_0'] = 'Standard Ticket'
        fields['form-0-default_price'] = '20.00'
        fields['payment_manualpayment__enabled'] = 'on'

        response = self.client.post(
            '/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug),
            fields,
            follow=False,
        )
        assert response.status_code == 200
        self.event1.refresh_from_db()
        with scopes_disabled():
            assert self.event1.products.count() == 0

    def test_quick_setup_save_continue_requires_payment_method_for_paid_tickets(self):
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        fields = extract_form_fields(doc.select('.container-fluid form')[0])
        fields['action'] = 'continue'
        fields['form-TOTAL_FORMS'] = '1'
        fields['form-INITIAL_FORMS'] = '1'
        fields['form-MIN_NUM_FORMS'] = '0'
        fields['form-MAX_NUM_FORMS'] = '1000'
        fields['form-0-name_0'] = 'Standard Ticket'
        fields['form-0-default_price'] = '20.00'
        fields['form-0-quota'] = '100'
        fields.pop('payment_banktransfer__enabled', None)
        fields.pop('payment_manualpayment__enabled', None)
        fields.pop('payment_stripe__enabled', None)
        fields.pop('payment_paypal__enabled', None)

        response = self.client.post(
            '/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug),
            fields,
            follow=False,
        )
        assert response.status_code == 200
        self.event1.refresh_from_db()
        with scopes_disabled():
            assert self.event1.products.count() == 0

    def test_quick_setup_save_continue_allowed_for_free_tickets_without_payment(self):
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        fields = extract_form_fields(doc.select('.container-fluid form')[0])
        fields['action'] = 'continue'
        fields['form-TOTAL_FORMS'] = '1'
        fields['form-INITIAL_FORMS'] = '1'
        fields['form-MIN_NUM_FORMS'] = '0'
        fields['form-MAX_NUM_FORMS'] = '1000'
        fields['form-0-name_0'] = 'Free Ticket'
        fields['form-0-default_price'] = '0.00'
        fields['form-0-quota'] = '100'
        fields.pop('payment_banktransfer__enabled', None)
        fields.pop('payment_manualpayment__enabled', None)
        fields.pop('payment_stripe__enabled', None)
        fields.pop('payment_paypal__enabled', None)

        response = self.client.post(
            '/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug),
            fields,
            follow=False,
        )
        assert response.status_code == 302
        assert response['Location'] == '/control/event/%s/%s/live/' % (self.orga1.slug, self.event1.slug)
        self.event1.refresh_from_db()
        with scopes_disabled():
            assert self.event1.products.count() == 1

    def test_quick_setup_checkout_access(self):
        doc = self.get_doc('/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug))
        fields = extract_form_fields(doc.select('.container-fluid form')[0])
        fields['require_registered_account_for_tickets'] = 'on'
        fields['form-TOTAL_FORMS'] = '1'
        fields['form-INITIAL_FORMS'] = '1'
        fields['form-MIN_NUM_FORMS'] = '0'
        fields['form-MAX_NUM_FORMS'] = '1000'
        fields['form-0-name_0'] = 'Standard Ticket'
        fields['form-0-default_price'] = '20.00'
        fields['form-0-quota'] = '100'
        fields['payment_banktransfer__enabled'] = 'on'
        fields['payment_banktransfer_bank_details_type'] = 'other'
        fields['payment_banktransfer_bank_details_0'] = 'Test bank details'

        doc = self.post_doc(
            '/control/event/%s/%s/quickstart/' % (self.orga1.slug, self.event1.slug),
            fields,
        )
        assert len(doc.select('.alert-success')) > 0
        self.event1.refresh_from_db()
        self.event1.settings.flush()
        assert self.event1.settings.require_registered_account_for_tickets

    def test_settings(self):
        doc = self.get_doc('/control/event/%s/%s/settings/' % (self.orga1.slug, self.event1.slug))
        doc.select('[name=date_to_0]')[0]['value'] = '2013-12-30'
        doc.select('[name=date_to_1]')[0]['value'] = '17:00:00'
        doc.select('[name=settings-max_items_per_order]')[0]['value'] = '12'

        doc = self.post_doc(
            '/control/event/%s/%s/settings/' % (self.orga1.slug, self.event1.slug),
            extract_form_fields(doc.select('.container-fluid form')[0]),
        )
        assert len(doc.select('.alert-success')) > 0
        assert doc.select('[name=date_to_0]')[0]['value'] == '2013-12-30'
        assert doc.select('[name=date_to_1]')[0]['value'] == '17:00:00'
        assert doc.select('[name=settings-max_items_per_order]')[0]['value'] == '12'

    def test_settings_timezone(self):
        doc = self.get_doc('/control/event/%s/%s/settings/' % (self.orga1.slug, self.event1.slug))
        doc.select('[name=date_to_0]')[0]['value'] = '2013-12-30'
        doc.select('[name=date_to_1]')[0]['value'] = '17:00:00'
        doc.select('[name=settings-max_items_per_order]')[0]['value'] = '12'
        doc.select('[name=settings-timezone]')[0]['value'] = 'Asia/Tokyo'
        doc.find('option', {'value': 'Asia/Tokyo'})['selected'] = 'selected'
        doc.find('option', {'value': 'UTC'}).attrs.pop('selected')

        doc = self.post_doc(
            '/control/event/%s/%s/settings/' % (self.orga1.slug, self.event1.slug),
            extract_form_fields(doc.select('.container-fluid form')[0]),
        )
        assert len(doc.select('.alert-success')) > 0
        # date_to should not be changed even though the timezone is changed
        assert doc.select('[name=date_to_0]')[0]['value'] == '2013-12-30'
        assert doc.select('[name=date_to_1]')[0]['value'] == '17:00:00'
        assert 'selected' in doc.find('option', {'value': 'Asia/Tokyo'}).attrs
        assert doc.select('[name=settings-max_items_per_order]')[0]['value'] == '12'

        self.event1.refresh_from_db()
        # Asia/Tokyo -> GMT+9
        assert self.event1.date_to.strftime('%Y-%m-%d %H:%M:%S') == '2013-12-30 08:00:00'
        assert self.event1.settings.timezone == 'Asia/Tokyo'

    def test_testmode_enable(self):
        self.event1.testmode = False
        self.event1.save()
        self.post_doc(
            '/control/event/%s/%s/live/' % (self.orga1.slug, self.event1.slug),
            {'testmode': 'true'},
        )
        self.event1.refresh_from_db()
        assert self.event1.testmode

    def test_testmode_disable(self):
        with scopes_disabled():
            o = Order.objects.create(
                code='FOO',
                event=self.event1,
                email='dummy@dummy.test',
                status=Order.STATUS_PENDING,
                datetime=now(),
                expires=now() + datetime.timedelta(days=10),
                total=14,
                locale='en',
                testmode=True,
            )
            o2 = Order.objects.create(
                code='FOO2',
                event=self.event1,
                email='dummy@dummy.test',
                status=Order.STATUS_PENDING,
                datetime=now(),
                expires=now() + datetime.timedelta(days=10),
                total=14,
                locale='en',
            )
            self.event1.testmode = True
            self.event1.save()
        self.post_doc(
            '/control/event/%s/%s/live/' % (self.orga1.slug, self.event1.slug),
            {'testmode': 'false'},
        )
        self.event1.refresh_from_db()
        assert not self.event1.testmode
        with scopes_disabled():
            assert Order.objects.filter(pk=o.pk).exists()
            assert Order.objects.filter(pk=o2.pk).exists()

    def test_testmode_disable_delete(self):
        with scopes_disabled():
            o = Order.objects.create(
                code='FOO',
                event=self.event1,
                email='dummy@dummy.test',
                status=Order.STATUS_PENDING,
                datetime=now(),
                expires=now() + datetime.timedelta(days=10),
                total=14,
                locale='en',
                testmode=True,
            )
            o2 = Order.objects.create(
                code='FOO2',
                event=self.event1,
                email='dummy@dummy.test',
                status=Order.STATUS_PENDING,
                datetime=now(),
                expires=now() + datetime.timedelta(days=10),
                total=14,
                locale='en',
            )
            self.event1.testmode = True
            self.event1.save()
        self.post_doc(
            '/control/event/%s/%s/live/' % (self.orga1.slug, self.event1.slug),
            {'testmode': 'false', 'delete': 'yes'},
        )
        self.event1.refresh_from_db()
        assert not self.event1.testmode
        with scopes_disabled():
            assert not Order.objects.filter(pk=o.pk).exists()
            assert Order.objects.filter(pk=o2.pk).exists()

    def test_live_disable(self):
        self.event1.live = True
        self.event1.save()
        self.post_doc(
            '/control/event/%s/%s/live/' % (self.orga1.slug, self.event1.slug),
            {'live': 'false'},
        )
        self.event1.refresh_from_db()
        assert not self.event1.live

    def test_live_ok(self):
        with scopes_disabled():
            self.event1.items.create(name='Test', default_price=5)
            self.event1.settings.set('payment_banktransfer__enabled', True)
            self.event1.quotas.create(name='Test quota')
        doc = self.get_doc('/control/event/%s/%s/live/' % (self.orga1.slug, self.event1.slug))
        assert len(doc.select('input[name=live]'))
        self.post_doc(
            '/control/event/%s/%s/live/' % (self.orga1.slug, self.event1.slug),
            {'live': 'true'},
        )
        self.event1.refresh_from_db()
        assert self.event1.live

    def test_live_dont_require_payment_method_free(self):
        with scopes_disabled():
            self.event1.items.create(name='Test', default_price=0)
            self.event1.settings.set('payment_banktransfer__enabled', False)
            self.event1.quotas.create(name='Test quota')
        doc = self.get_doc('/control/event/%s/%s/live/' % (self.orga1.slug, self.event1.slug))
        assert len(doc.select('input[name=live]'))

    def test_live_require_payment_method(self):
        with scopes_disabled():
            self.event1.items.create(name='Test', default_price=5)
            self.event1.settings.set('payment_banktransfer__enabled', False)
            self.event1.quotas.create(name='Test quota')
        doc = self.get_doc('/control/event/%s/%s/live/' % (self.orga1.slug, self.event1.slug))
        assert len(doc.select('input[name=live]')) == 0

    def test_live_require_a_quota(self):
        self.event1.settings.set('payment_banktransfer__enabled', True)
        doc = self.get_doc('/control/event/%s/%s/live/' % (self.orga1.slug, self.event1.slug))
        assert len(doc.select('input[name=live]')) == 0

    def test_payment_settings_provider(self):
        self.get_doc('/control/event/%s/%s/settings/payment/banktransfer' % (self.orga1.slug, self.event1.slug))
        self.post_doc(
            '/control/event/%s/%s/settings/payment/banktransfer' % (self.orga1.slug, self.event1.slug),
            {
                'payment_banktransfer__enabled': 'true',
                'payment_banktransfer_ack': 'true',
                'payment_banktransfer__fee_abs': '12.23',
                'payment_banktransfer_bank_details_type': 'other',
                'payment_banktransfer_bank_details_0': 'Test',
                'payment_banktransfer__restrict_to_sales_channels': ['web'],
            },
        )
        self.event1.settings.flush()
        assert self.event1.settings.get('payment_banktransfer__enabled', as_type=bool)
        assert self.event1.settings.get('payment_banktransfer__fee_abs', as_type=Decimal) == Decimal('12.23')

    def test_payment_settings(self):
        tr19 = self.event1.tax_rules.create(rate=Decimal('19.00'))
        self.get_doc('/control/event/%s/%s/settings/payment' % (self.orga1.slug, self.event1.slug))
        self.post_doc(
            '/control/event/%s/%s/settings/payment' % (self.orga1.slug, self.event1.slug),
            {
                'payment_term_days': '2',
                'payment_term_minutes': '30',
                'payment_term_mode': 'days',
                'tax_rate_default': tr19.pk,
            },
        )
        self.event1.settings.flush()
        assert self.event1.settings.get('payment_term_days', as_type=int) == 2

    def test_payment_settings_last_date_payment_after_presale_end(self):
        tr19 = self.event1.tax_rules.create(rate=Decimal('19.00'))
        self.event1.presale_end = now()
        self.event1.save(update_fields=['presale_end'])
        doc = self.post_doc(
            '/control/event/%s/%s/settings/payment' % (self.orga1.slug, self.event1.slug),
            {
                'payment_term_days': '2',
                'payment_term_last_0': 'absolute',
                'payment_term_last_1': (self.event1.presale_end - datetime.timedelta(1)).strftime('%Y-%m-%d'),
                'payment_term_last_2': '0',
                'payment_term_last_3': 'date_from',
                'tax_rate_default': tr19.pk,
            },
        )
        assert doc.select('.alert-danger')
        self.event1.presale_end = None
        self.event1.save(update_fields=['presale_end'])

    def test_payment_settings_relative_date_payment_after_presale_end(self):
        with scopes_disabled():
            tr19 = self.event1.tax_rules.create(rate=Decimal('19.00'))
        self.event1.presale_end = self.event1.date_from - datetime.timedelta(days=5)
        self.event1.save(update_fields=['presale_end'])
        doc = self.post_doc(
            '/control/event/%s/%s/settings/payment' % (self.orga1.slug, self.event1.slug),
            {
                'payment_term_days': '2',
                'payment_term_last_0': 'relative',
                'payment_term_last_1': '',
                'payment_term_last_2': '10',
                'payment_term_last_3': 'date_from',
                'tax_rate_default': tr19.pk,
            },
        )
        assert doc.select('.alert-danger')
        self.event1.presale_end = None
        self.event1.save(update_fields=['presale_end'])

    def test_invoice_settings(self):
        doc = self.get_doc('/control/event/%s/%s/settings/invoice' % (self.orga1.slug, self.event1.slug))
        data = extract_form_fields(doc.select('form')[0])
        data['invoice_address_required'] = 'on'
        doc = self.post_doc(
            '/control/event/%s/%s/settings/invoice' % (self.orga1.slug, self.event1.slug),
            data,
            follow=True,
        )
        assert doc.select('.alert-success')
        self.event1.settings.flush()
        assert self.event1.settings.get('invoice_address_required', as_type=bool)

    def test_display_settings(self):
        with mocker_context() as mocker:
            mocked = mocker.patch('eventyay.presale.style.regenerate_css.apply_async')

            doc = self.get_doc('/control/event/%s/%s/settings/' % (self.orga1.slug, self.event1.slug))
            data = extract_form_fields(doc.select('form')[0])
            data['settings-primary_color'] = '#000000'
            doc = self.post_doc(
                '/control/event/%s/%s/settings/' % (self.orga1.slug, self.event1.slug),
                data,
                follow=True,
            )
            assert doc.select('.alert-success')
            self.event1.settings.flush()
            assert self.event1.settings.get('primary_color') == '#000000'
            mocked.assert_any_call(args=(self.event1.pk,))

    def test_display_settings_do_not_override_parent(self):
        self.orga1.settings.primary_color = '#000000'
        doc = self.get_doc('/control/event/%s/%s/settings/' % (self.orga1.slug, self.event1.slug))
        data = extract_form_fields(doc.select('form')[0])
        doc = self.post_doc(
            '/control/event/%s/%s/settings/' % (self.orga1.slug, self.event1.slug),
            data,
            follow=True,
        )
        assert doc.select('.alert-success')
        self.event1.settings.flush()
        assert 'primary_color' not in self.event1.settings._cache()
        assert self.event1.settings.primary_color == self.orga1.settings.primary_color

    def test_display_settings_explicitly_override_parent(self):
        self.orga1.settings.primary_color = '#000000'

        doc = self.get_doc('/control/event/%s/%s/settings/' % (self.orga1.slug, self.event1.slug))
        data = extract_form_fields(doc.select('form')[0])
        data['decouple'] = 'primary_color'
        doc = self.post_doc(
            '/control/event/%s/%s/settings/' % (self.orga1.slug, self.event1.slug),
            data,
            follow=True,
        )
        assert doc.select('.alert-success')
        self.event1.settings.flush()
        assert 'primary_color' in self.event1.settings._cache()
        assert self.event1.settings.primary_color == self.orga1.settings.primary_color

    def test_email_settings(self):
        with mocker_context() as mocker:
            mocked = mocker.patch('eventyay.base.email.CustomSMTPBackend.test')

            doc = self.get_doc('/control/event/%s/%s/settings/email' % (self.orga1.slug, self.event1.slug))
            data = extract_form_fields(doc.select('form')[0])
            data['test'] = '1'
            data['email_vendor'] = 'smtp'
            data['send_grid_api_key'] = 'dummy_key'
            doc = self.post_doc(
                '/control/event/%s/%s/settings/email' % (self.orga1.slug, self.event1.slug),
                data,
                follow=True,
            )
            assert doc.select('.alert-success')
            self.event1.settings.flush()
            assert mocked.called

    def test_ticket_settings(self):
        doc = self.get_doc('/control/event/%s/%s/settings/tickets' % (self.orga1.slug, self.event1.slug))
        data = extract_form_fields(doc.select('form')[0])
        data['ticket_download'] = 'on'
        data['ticketoutput_testdummy__enabled'] = 'on'
        doc = self.post_doc(
            '/control/event/%s/%s/settings/tickets' % (self.orga1.slug, self.event1.slug),
            data,
            follow=True,
        )
        self.event1.settings.flush()
        assert self.event1.settings.get('ticket_download', as_type=bool)

    def test_create_event_unauthorized(self):
        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga2.pk,
                'foundation-locales': ('en', 'de'),
            },
        )
        assert doc.select('.has-error')

    def test_create_event_slug_url_options_for_multiple_organizers(self):
        team = Team.objects.create(organizer=self.orga2, can_create_events=True)
        team.members.add(self.user)

        doc = self.get_doc('/control/events/add')
        slug_options = json.loads(doc.select('#event-create-organizers')[0].text)

        assert slug_options[str(self.orga1.pk)]['prefix'].endswith('/ccc/')
        assert slug_options[str(self.orga2.pk)]['prefix'].endswith('/mrm/')
        assert slug_options[str(self.orga1.pk)]['rngUrl'].endswith('/organizer/ccc/slugrng')
        assert slug_options[str(self.orga2.pk)]['rngUrl'].endswith('/organizer/mrm/slugrng')
        assert doc.select('.slug-widget-prefix')[0].text == ''
        assert 'disabled' in doc.select('#event-slug-random-generate')[0].attrs

    def test_create_event_slug_url_uses_selected_organizer(self):
        team = Team.objects.create(organizer=self.orga2, can_create_events=True)
        team.members.add(self.user)

        doc = self.get_doc('/control/events/add?organizer=mrm')

        assert doc.select('.slug-widget-prefix')[0].text.endswith('/mrm/')
        assert doc.select('#event-slug-random-generate')[0]['data-rng-url'].endswith('/organizer/mrm/slugrng')

    def test_create_invalid_default_language_fallback(self):
        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': ('de',),
            },
        )

        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': '33C3',
                'basics-name_1': '33C3',
                'basics-slug': '33c3-invalid-lang',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2016-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Hamburg',
                'basics-location_1': 'Hamburg',
                'basics-currency': 'EUR',
                'basics-tax_rate': '',
                'basics-locale': 'en',
                'basics-timezone': 'Europe/Berlin',
                'basics-presale_start_0': '2016-11-01',
                'basics-presale_start_1': '10:00:00',
                'basics-presale_end_0': '2016-11-30',
                'basics-presale_end_1': '18:00:00',
            },
        )
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'copy',
                'event_wizard-prefix': 'event_wizard',
                'copy-copy_from_event': '',
            },
        )
        with scopes_disabled():
            ev = Event.objects.get(slug='33c3-invalid-lang')
            assert ev.settings.locale == 'de'

    def test_create_event_first_locale_becomes_default(self):
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': ('de', 'en'),
            },
        )

        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': 'Default Lang Event',
                'basics-slug': 'default-lang-event',
                'basics-date_from_0': '2026-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2026-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Berlin',
                'basics-currency': 'EUR',
                'basics-timezone': 'Europe/Berlin',
            },
        )

        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'copy',
                'event_wizard-prefix': 'event_wizard',
                'copy-copy_from_event': '',
            },
        )

        with scopes_disabled():
            ev = Event.objects.get(slug='default-lang-event')
            assert ev.settings.locales == ['de', 'en']
            assert ev.settings.locale == 'de'

    def test_create_event_reordering_sets_default(self):
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': ('en', 'de'),
            },
        )

        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': 'Reordered Lang Event',
                'basics-slug': 'reordered-lang-event',
                'basics-date_from_0': '2026-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2026-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Berlin',
                'basics-currency': 'EUR',
                'basics-locale': 'de',  # Set by drag-and-drop tray in JS
                'basics-timezone': 'Europe/Berlin',
            },
        )

        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'copy',
                'event_wizard-prefix': 'event_wizard',
                'copy-copy_from_event': '',
            },
        )

        with scopes_disabled():
            ev = Event.objects.get(slug='reordered-lang-event')
            assert ev.settings.locale == 'de'

    def test_create_event_without_locales_returns_validation_error(self):
        response = self.client.post(
            '/common/events/add',
            {
                'foundation-organizer': self.orga1.pk,
                'basics-locale': 'en',
                'basics-name_0': 'No Locales',
                'basics-slug': 'no-locales-test',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2016-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Berlin',
                'basics-currency': 'EUR',
                'basics-timezone': 'Europe/Berlin',
            },
        )
        self.assertEqual(response.status_code, 200)
        foundation_form = response.context['foundation_form']
        self.assertIn('locales', foundation_form.errors)

    def test_create_event_defaults_locale_from_selected_languages(self):
        response = self.client.post(
            '/common/events/add',
            {
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': 'en',
                'basics-locale': '',
                'basics-name_0': 'Default English',
                'basics-slug': 'default-english-event',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2016-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Berlin',
                'basics-currency': 'EUR',
                'basics-timezone': 'Europe/Berlin',
            },
        )
        self.assertEqual(response.status_code, 302)
        with scopes_disabled():
            ev = Event.objects.get(slug='default-english-event')
            assert ev.settings.locale == 'en'

    def test_create_duplicate_slug(self):
        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-prefix': 'event_wizard',
                'event_wizard-current_step': 'foundation',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': ('de', 'en'),
            },
        )

        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': '33C3',
                'basics-name_1': '33C3',
                'basics-slug': '31c3',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2016-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Hamburg',
                'basics-location_1': 'Hamburg',
                'basics-currency': 'EUR',
                'basics-tax_rate': '',
                'basics-locale': 'en',
                'basics-timezone': 'Europe/Berlin',
                'basics-presale_start_0': '2016-11-01',
                'basics-presale_start_1': '10:00:00',
                'basics-presale_end_0': '2016-11-30',
                'basics-presale_end_1': '18:00:00',
            },
        )
        assert doc.select('.has-error')

    def test_create_event_success(self):
        doc = self.get_doc('/control/events/add')

        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': ('en', 'de'),
            },
        )
        assert doc.select('#id_basics-name_0')
        assert doc.select('#id_basics-name_1')

        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': '33C3',
                'basics-name_1': '33C3',
                'basics-slug': '33c3',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2016-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Hamburg',
                'basics-location_1': 'Hamburg',
                'basics-currency': 'EUR',
                'basics-tax_rate': '19.00',
                'basics-locale': 'en',
                'basics-timezone': 'Europe/Berlin',
                'basics-presale_start_0': '2016-11-01',
                'basics-presale_start_1': '10:00:00',
                'basics-presale_end_0': '2016-11-30',
                'basics-presale_end_1': '18:00:00',
                'basics-team': '',
            },
        )

        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'copy',
                'event_wizard-prefix': 'event_wizard',
                'copy-copy_from_event': '',
            },
        )

        with scopes_disabled():
            ev = Event.objects.get(slug='33c3')
            assert ev.name == LazyI18nString({'de': '33C3', 'en': '33C3'})
            assert ev.settings.locales == ['en', 'de']
            assert ev.settings.locale == 'en'
            assert ev.currency == 'EUR'
            assert ev.settings.timezone == 'Europe/Berlin'
            assert ev.organizer == self.orga1
            assert ev.location == LazyI18nString({'de': 'Hamburg', 'en': 'Hamburg'})
            assert Team.objects.filter(limit_events=ev, members=self.user).exists()

            berlin_tz = ZoneInfo('Europe/Berlin')
            assert ev.date_from == datetime.datetime(2016, 12, 27, 10, 0, 0, tzinfo=berlin_tz).astimezone(datetime.timezone.utc)
            assert ev.date_to == datetime.datetime(2016, 12, 30, 19, 0, 0, tzinfo=berlin_tz).astimezone(datetime.timezone.utc)
            assert ev.presale_start == datetime.datetime(2016, 11, 1, 10, 0, 0, tzinfo=berlin_tz).astimezone(datetime.timezone.utc)
            assert ev.presale_end == datetime.datetime(2016, 11, 30, 18, 0, 0, tzinfo=berlin_tz).astimezone(datetime.timezone.utc)

            assert ev.tax_rules.filter(rate=Decimal('19.00')).exists()

    def test_create_event_with_subevents_success(self):
        doc = self.get_doc('/control/events/add')
        tabletext = doc.select('form')[0].text
        self.assertIn('CCC', tabletext)
        self.assertNotIn('MRM', tabletext)

        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-prefix': 'event_wizard',
                'event_wizard-current_step': 'foundation',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': ('en', 'de'),
                'foundation-has_subevents': 'on',
            },
        )
        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': '33C3',
                'basics-name_1': '33C3',
                'basics-slug': '33c3',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2016-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Hamburg',
                'basics-location_1': 'Hamburg',
                'basics-currency': 'EUR',
                'basics-tax_rate': '',
                'basics-locale': 'en',
                'basics-timezone': 'Europe/Berlin',
                'basics-presale_start_0': '2016-11-01',
                'basics-presale_start_1': '10:00:00',
                'basics-presale_end_0': '2016-11-30',
                'basics-presale_end_1': '18:00:00',
                'basics-team': '',
            },
        )
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'copy',
                'event_wizard-prefix': 'event_wizard',
                'copy-copy_from_event': '',
            },
        )
        with scopes_disabled():
            ev = Event.objects.get(slug='33c3')
            assert ev.has_subevents
            assert ev.subevents.count() == 0

    def test_create_event_copy_success(self):
        with scopes_disabled():
            tr = self.event1.tax_rules.create(rate=19, name='VAT')
            q1 = self.event1.quotas.create(
                name='Foo',
                size=0,
            )
            self.event1.items.create(
                name='Early-bird ticket',
                category=None,
                default_price=23,
                tax_rule=tr,
                admission=True,
                hidden_if_available=q1,
            )
            self.event1.settings.tax_rate_default = tr
        doc = self.get_doc('/control/events/add')

        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': ('en', 'de'),
            },
        )
        assert doc.select('#id_basics-name_0')
        assert doc.select('#id_basics-name_1')

        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': '33C3',
                'basics-name_1': '33C3',
                'basics-slug': '33c3',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2016-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Hamburg',
                'basics-location_1': 'Hamburg',
                'basics-currency': 'EUR',
                'basics-tax_rate': '19.00',
                'basics-locale': 'en',
                'basics-timezone': 'Europe/Berlin',
                'basics-presale_start_0': '2016-11-01',
                'basics-presale_start_1': '10:00:00',
                'basics-presale_end_0': '2016-11-30',
                'basics-presale_end_1': '18:00:00',
            },
        )

        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'copy',
                'event_wizard-prefix': 'event_wizard',
                'copy-copy_from_event': self.event1.pk,
            },
        )

        with scopes_disabled():
            ev = Event.objects.get(slug='33c3')
            assert ev.name == LazyI18nString({'de': '33C3', 'en': '33C3'})
            assert ev.settings.locales == ['en', 'de']
            assert ev.settings.locale == 'en'
            assert ev.currency == 'EUR'
            assert ev.settings.timezone == 'Europe/Berlin'
            assert ev.organizer == self.orga1
            assert ev.location == LazyI18nString({'de': 'Hamburg', 'en': 'Hamburg'})
            assert Team.objects.filter(limit_events=ev, members=self.user).exists()
            assert ev.items.count() == 1

            berlin_tz = ZoneInfo('Europe/Berlin')
            assert ev.date_from == datetime.datetime(2016, 12, 27, 10, 0, 0, tzinfo=berlin_tz).astimezone(datetime.timezone.utc)
            assert ev.date_to == datetime.datetime(2016, 12, 30, 19, 0, 0, tzinfo=berlin_tz).astimezone(datetime.timezone.utc)
            assert ev.presale_start == datetime.datetime(2016, 11, 1, 10, 0, 0, tzinfo=berlin_tz).astimezone(datetime.timezone.utc)
            assert ev.presale_end == datetime.datetime(2016, 11, 30, 18, 0, 0, tzinfo=berlin_tz).astimezone(datetime.timezone.utc)

            assert ev.tax_rules.filter(rate=Decimal('19.00')).count() == 1
            i = ev.items.get()
            assert i.hidden_if_available.name == 'Foo'
            assert i.hidden_if_available.event == ev
            assert i.hidden_if_available.pk != q1.pk

    def test_create_event_clone_success(self):
        with scopes_disabled():
            tr = self.event1.tax_rules.create(rate=19, name='VAT')
            self.event1.items.create(
                name='Early-bird ticket',
                category=None,
                default_price=23,
                tax_rule=tr,
                admission=True,
            )
        self.event1.settings.tax_rate_default = tr
        doc = self.get_doc('/control/events/add?clone=' + str(self.event1.pk))
        tabletext = doc.select('form')[0].text
        self.assertIn('CCC', tabletext)
        self.assertNotIn('MRM', tabletext)

        doc = self.post_doc(
            '/control/events/add?clone=' + str(self.event1.pk),
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': ('en', 'de'),
            },
        )
        assert doc.select('#id_basics-date_from_0')[0]['value'] == '2013-12-26'

        doc = self.post_doc(
            '/control/events/add?clone=' + str(self.event1.pk),
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': '33C3',
                'basics-name_1': '33C3',
                'basics-slug': '33c3',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2016-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Hamburg',
                'basics-location_1': 'Hamburg',
                'basics-currency': 'EUR',
                'basics-tax_rate': '19.00',
                'basics-locale': 'en',
                'basics-timezone': 'Europe/Berlin',
                'basics-presale_start_0': '2016-11-01',
                'basics-presale_start_1': '10:00:00',
                'basics-presale_end_0': '2016-11-30',
                'basics-presale_end_1': '18:00:00',
                'basics-team': '',
            },
        )

        assert not doc.select('#id_copy-copy_from_event_1')

        with scopes_disabled():
            ev = Event.objects.get(slug='33c3')
            assert ev.name == LazyI18nString({'de': '33C3', 'en': '33C3'})
            assert ev.settings.locales == ['en', 'de']
            assert ev.settings.locale == 'en'
            assert ev.currency == 'EUR'
            assert ev.settings.timezone == 'Europe/Berlin'
            assert ev.organizer == self.orga1
            assert ev.location == LazyI18nString({'de': 'Hamburg', 'en': 'Hamburg'})
            assert Team.objects.filter(limit_events=ev, members=self.user).exists()
            assert ev.items.count() == 1

            berlin_tz = ZoneInfo('Europe/Berlin')
            assert ev.date_from == datetime.datetime(2016, 12, 27, 10, 0, 0, tzinfo=berlin_tz).astimezone(datetime.timezone.utc)
            assert ev.date_to == datetime.datetime(2016, 12, 30, 19, 0, 0, tzinfo=berlin_tz).astimezone(datetime.timezone.utc)
            assert ev.presale_start == datetime.datetime(2016, 11, 1, 10, 0, 0, tzinfo=berlin_tz).astimezone(datetime.timezone.utc)
            assert ev.presale_end == datetime.datetime(2016, 11, 30, 18, 0, 0, tzinfo=berlin_tz).astimezone(datetime.timezone.utc)

            assert ev.tax_rules.filter(rate=Decimal('19.00')).count() == 1

    def test_create_event_only_date_from(self):
        # date_to, presale_start & presale_end are optional fields
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': 'en',
            },
        )
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': '33C3',
                'basics-slug': '33c3',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '',
                'basics-date_to_1': '',
                'basics-location_0': 'Hamburg',
                'basics-currency': 'EUR',
                'basics-tax_rate': '',
                'basics-locale': 'en',
                'basics-timezone': 'UTC',
                'basics-presale_start_0': '',
                'basics-presale_start_1': '',
                'basics-presale_end_0': '',
                'basics-presale_end_1': '',
                'basics-team': '',
            },
        )
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'copy',
                'event_wizard-prefix': 'event_wizard',
                'copy-copy_from_event': '',
            },
        )

        with scopes_disabled():
            ev = Event.objects.get(slug='33c3')
            assert ev.name == LazyI18nString({'en': '33C3'})
            assert ev.settings.locales == ['en']
            assert ev.settings.locale == 'en'
            assert ev.currency == 'EUR'
            assert ev.settings.timezone == 'UTC'
            assert ev.organizer == self.orga1
            assert ev.location == LazyI18nString({'en': 'Hamburg'})
            assert Team.objects.filter(limit_events=ev, members=self.user).exists()
            assert ev.date_from == datetime.datetime(2016, 12, 27, 10, 0, 0, tzinfo=datetime.timezone.utc)
            assert ev.date_to is None
            assert ev.presale_start is None
            assert ev.presale_end is None

    def test_create_event_existing_team(self):
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': 'en',
            },
        )
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': '33C3',
                'basics-slug': '33c3',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '',
                'basics-date_to_1': '',
                'basics-location_0': 'Hamburg',
                'basics-currency': 'EUR',
                'basics-tax_rate': '',
                'basics-locale': 'en',
                'basics-timezone': 'UTC',
                'basics-presale_start_0': '',
                'basics-presale_start_1': '',
                'basics-presale_end_0': '',
                'basics-presale_end_1': '',
                'basics-team': str(self.team2.pk),
            },
        )
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'copy',
                'event_wizard-prefix': 'event_wizard',
                'copy-copy_from_event': '',
            },
        )

        with scopes_disabled():
            ev = Event.objects.get(slug='33c3')
            assert ev.name == LazyI18nString({'en': '33C3'})
            assert ev.settings.locales == ['en']
            assert ev.settings.locale == 'en'
            assert ev.currency == 'EUR'
            assert ev.settings.timezone == 'UTC'
            assert ev.organizer == self.orga1
            assert ev.location == LazyI18nString({'en': 'Hamburg'})
            team = Team.objects.filter(limit_events=ev, members=self.user).first()
            assert team == self.team2
            assert ev.date_from == datetime.datetime(2016, 12, 27, 10, 0, 0, tzinfo=datetime.timezone.utc)
            assert ev.date_to is None
            assert ev.presale_start is None
            assert ev.presale_end is None

    def test_create_event_missing_date_from(self):
        # date_from is mandatory
        self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': 'en',
            },
        )
        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': '33C3',
                'basics-slug': '33c3',
                'basics-date_from_0': '',
                'basics-date_from_1': '',
                'basics-date_to_0': '2016-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Hamburg',
                'basics-currency': 'EUR',
                'basics-tax_rate': '',
                'basics-locale': 'en',
                'basics-timezone': 'Europe/Berlin',
                'basics-presale_start_0': '2016-11-01',
                'basics-presale_start_1': '10:00:00',
                'basics-presale_end_0': '2016-11-30',
                'basics-presale_end_1': '18:00:00',
            },
        )
        assert doc.select('.has-error')

    def test_create_event_currency_symbol(self):
        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': 'en',
            },
        )

        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': '33C3',
                'basics-slug': '31c4',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2016-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Hamburg',
                'basics-currency': '$',
                'basics-tax_rate': '',
                'basics-locale': 'en',
                'basics-timezone': 'Europe/Berlin',
                'basics-presale_start_0': '2016-11-01',
                'basics-presale_start_1': '10:00:00',
                'basics-presale_end_0': '2016-11-30',
                'basics-presale_end_1': '18:00:00',
            },
        )
        assert doc.select('.has-error')

    def test_create_event_non_iso_currency(self):
        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'foundation',
                'event_wizard-prefix': 'event_wizard',
                'foundation-organizer': self.orga1.pk,
                'foundation-locales': 'en',
            },
        )

        doc = self.post_doc(
            '/control/events/add',
            {
                'event_wizard-current_step': 'basics',
                'event_wizard-prefix': 'event_wizard',
                'basics-name_0': '33C3',
                'basics-slug': '31c5',
                'basics-date_from_0': '2016-12-27',
                'basics-date_from_1': '10:00:00',
                'basics-date_to_0': '2016-12-30',
                'basics-date_to_1': '19:00:00',
                'basics-location_0': 'Hamburg',
                'basics-currency': 'ASD',
                'basics-tax_rate': '',
                'basics-locale': 'en',
                'basics-timezone': 'Europe/Berlin',
                'basics-presale_start_0': '2016-11-01',
                'basics-presale_start_1': '10:00:00',
                'basics-presale_end_0': '2016-11-30',
                'basics-presale_end_1': '18:00:00',
            },
        )
        assert doc.select('.has-error')


class EventDeletionTest(SoupTest):
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        self.orga1 = Organizer.objects.create(name='CCC', slug='ccc')
        self.event1 = Event.objects.create(
            organizer=self.orga1,
            name='30C3',
            slug='30c3',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
            plugins='eventyay.plugins.banktransfer,tests.tickets.testdummy',
            has_subevents=False,
        )

        t = Team.objects.create(
            organizer=self.orga1,
            can_create_events=True,
            can_change_event_settings=True,
            can_change_items=True,
        )
        t.members.add(self.user)
        t.limit_events.add(self.event1)
        self.ticket = self.event1.items.create(
            name='Early-bird ticket', category=None, default_price=23, admission=True
        )

        self.client.login(email='dummy@dummy.dummy', password='dummy')

    def test_delete_allowed(self):
        session = self.client.session
        session['pretix_auth_login_time'] = int(time.time())
        session.save()
        self.client.post('/control/event/ccc/30c3/delete/', {'slug': '30c3'})

        with scopes_disabled():
            assert not self.orga1.events.exists()

    def test_delete_wrong_slug(self):
        self.post_doc('/control/event/ccc/30c3/delete/', {'user_pw': 'dummy', 'slug': '31c3'})
        with scopes_disabled():
            assert self.orga1.events.exists()

    def test_delete_wrong_pw(self):
        self.post_doc('/control/event/ccc/30c3/delete/', {'user_pw': 'invalid', 'slug': '30c3'})
        with scopes_disabled():
            assert self.orga1.events.exists()

    def test_delete_orders(self):
        Order.objects.create(
            code='FOO',
            event=self.event1,
            email='dummy@dummy.test',
            status=Order.STATUS_PENDING,
            datetime=now(),
            expires=now(),
            total=14,
            locale='en',
        )
        self.post_doc('/control/event/ccc/30c3/delete/', {'user_pw': 'dummy', 'slug': '30c3'})
        with scopes_disabled():
            assert self.orga1.events.exists()
