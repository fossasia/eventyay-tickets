from decimal import Decimal

import pytest
from django.urls import resolve, reverse
from django.utils.timezone import now

from eventyay.base.models import User
from eventyay.base.settings import GlobalSettingsObject
from eventyay.control.forms.global_settings import (
    GlobalBusinessSettingsForm,
    GlobalSettingsForm,
)
from eventyay.control.navigation import get_admin_navigation


@pytest.fixture
def admin_user():
    return User.objects.create_user('admin@example.com', 'dummy', is_staff=True)


@pytest.fixture
def staff_client(client, admin_user):
    client.force_login(admin_user)
    admin_user.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    return client


@pytest.mark.django_db
class TestAdminNavigationBusiness:
    def test_admin_sidebar_has_business_top_level_and_subitems(self, rf, admin_user):
        request = rf.get('/admin/global/business/')
        request.user = admin_user
        request.resolver_match = resolve('/admin/global/business/')

        nav = get_admin_navigation(request)
        labels = [str(item.get('label')) for item in nav]
        assert labels == [
            'Global settings',
            'Business',
            'Task management',
            'Video',
            'Platform Data',
            'Users',
        ]

        business_item = next((item for item in nav if str(item.get('label')) == 'Business'), None)
        assert business_item is not None
        assert business_item['active'] is True
        assert business_item.get('icon') == 'briefcase'

        child_labels = [str(c['label']) for c in business_item['children']]
        assert child_labels == ['Business Settings', 'Event vouchers']

        settings_child = next(c for c in business_item['children'] if str(c['label']) == 'Business Settings')
        assert settings_child['url'] == reverse('eventyay_admin:admin.global.business')
        assert settings_child['active'] is True

        vouchers_child = next(c for c in business_item['children'] if str(c['label']) == 'Event vouchers')
        assert vouchers_child['url'] == reverse('eventyay_admin:admin.vouchers')
        assert vouchers_child['active'] is False


@pytest.mark.django_db
class TestBusinessSettingsPermissions:
    def test_anonymous_redirected_to_login(self, client):
        url = reverse('eventyay_admin:admin.global.business')
        response = client.get(url)
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_non_staff_forbidden(self, client):
        user = User.objects.create_user('regular@example.com', 'dummy')
        client.force_login(user)
        url = reverse('eventyay_admin:admin.global.business')
        response = client.get(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestBusinessSettingsView:
    def test_business_page_renders_only_three_tabs(self, staff_client):
        url = reverse('eventyay_admin:admin.global.business')
        response = staff_client.get(url)
        assert response.status_code == 200

        content = response.content.decode('utf-8')
        # Check page heading and the ONLY 3 tab fieldset IDs exist
        assert '<h1>Business Settings</h1>' in content
        assert 'id="tab-organizer_billing"' in content
        assert 'id="tab-ticket_fee"' in content
        assert 'id="tab-billing_validation"' in content
        assert 'id="tab-event_vouchers"' not in content

        # Check Organizer Billing texts and fields
        assert 'Stripe — Organizer Billing' in content
        assert 'This configuration is used for organiser billing and platform fee collection.' in content
        assert 'payment_stripe_publishable_key' in content
        assert 'payment_stripe_secret_key' in content
        assert 'payment_stripe_test_publishable_key' in content
        assert 'payment_stripe_test_secret_key' in content
        assert 'stripe_webhook_secret_key' in content

        # Check Ticket Fee and Billing Validation fields
        assert 'ticket_fee_percentage' in content
        assert 'billing_validation' in content

    def test_business_settings_save(self, staff_client):
        url = reverse('eventyay_admin:admin.global.business')
        post_data = {
            'payment_stripe_publishable_key': 'pk_live_business_test_123',
            'payment_stripe_secret_key': 'sk_live_business_test_123',
            'payment_stripe_test_publishable_key': 'pk_test_business_test_123',
            'payment_stripe_test_secret_key': 'sk_test_business_test_123',
            'stripe_webhook_secret_key': 'whsec_business_test_123',
            'ticket_fee_percentage': '3.50',
            'billing_validation': 'on',
        }
        response = staff_client.post(url, post_data)
        assert response.status_code == 302
        assert response['Location'] == reverse('eventyay_admin:admin.global.business')

        gs = GlobalSettingsObject()
        assert gs.settings.get('payment_stripe_publishable_key') == 'pk_live_business_test_123'
        assert gs.settings.get('ticket_fee_percentage', as_type=Decimal) == Decimal('3.50')
        assert gs.settings.get('billing_validation', as_type=bool) is True


@pytest.mark.django_db
class TestGlobalSettingsCleanUp:
    def test_global_settings_does_not_contain_moved_fields(self, staff_client):
        url = reverse('eventyay_admin:admin.global.settings')
        response = staff_client.get(url)
        assert response.status_code == 200

        content = response.content.decode('utf-8')
        # Stripe Organizer Billing should NOT be in Global Settings
        assert 'Stripe — Organizer Billing' not in content
        assert 'payment_stripe_publishable_key' not in content
        assert 'payment_stripe_secret_key' not in content
        assert 'stripe_webhook_secret_key' not in content

        # Ticket Fee and Billing Validation tabs should NOT be in Global Settings
        assert 'id="tab-ticket_fee"' not in content
        assert 'id="tab-billing_validation"' not in content
        assert 'id="tab-organizer_billing"' not in content

        # Payment Gateways should be moved to Ticketing page, not in Global Settings
        assert 'id="tab-payment_gateways"' not in content
        assert 'id="tab-payment-gateways"' not in content

        # Verify Ticketing page contains ticket payments
        ticketing_url = reverse('eventyay_admin:admin.global.ticketing')
        ticketing_resp = staff_client.get(ticketing_url)
        assert ticketing_resp.status_code == 200
        ticketing_content = ticketing_resp.content.decode('utf-8')
        assert 'id="tab-payment-gateways"' in ticketing_content
        assert 'Stripe — Ticket Payments' in ticketing_content
        assert 'PayPal — Ticket Payments' in ticketing_content
        assert 'payment_stripe_connect_client_id' in ticketing_content
        assert 'payment_stripe_connect_publishable_key' in ticketing_content
        assert 'payment_paypal_connect_client_id' in ticketing_content

    def test_global_settings_redirects_for_legacy_tabs(self, staff_client):
        url = reverse('eventyay_admin:admin.global.settings')

        for tab in ('organizer_billing', 'ticket_fee', 'billing_validation'):
            response = staff_client.get(f'{url}?tab={tab}')
            assert response.status_code == 302
            assert response['Location'] == f"{reverse('eventyay_admin:admin.global.business')}#tab-{tab}"

        for tab in ('vouchers', 'event_vouchers'):
            response = staff_client.get(f'{url}?tab={tab}')
            assert response.status_code == 302
            assert response['Location'] == reverse('eventyay_admin:admin.vouchers')


@pytest.mark.django_db
class TestFormStructures:
    def test_global_business_settings_form_fields(self):
        form = GlobalBusinessSettingsForm()
        expected_fields = {
            'payment_stripe_publishable_key',
            'payment_stripe_secret_key',
            'payment_stripe_test_publishable_key',
            'payment_stripe_test_secret_key',
            'stripe_webhook_secret_key',
            'ticket_fee_percentage',
            'billing_validation',
        }
        assert set(form.fields.keys()) == expected_fields
        groups = [g[0] for g in form.field_groups]
        assert groups == ['organizer_billing', 'ticket_fee', 'billing_validation']

    def test_global_settings_form_does_not_contain_business_fields(self):
        form = GlobalSettingsForm()
        business_fields = {
            'payment_stripe_publishable_key',
            'payment_stripe_secret_key',
            'payment_stripe_test_publishable_key',
            'payment_stripe_test_secret_key',
            'stripe_webhook_secret_key',
            'ticket_fee_percentage',
            'billing_validation',
        }
        for field in business_fields:
            assert field not in form.fields
        groups = [g[0] for g in form.field_groups]
        assert 'ticket_fee' not in groups
        assert 'billing_validation' not in groups
