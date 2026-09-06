from collections import OrderedDict
from decimal import Decimal
from unittest.mock import patch

import pytest
from django import forms as dj_forms
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.models import User
from eventyay.base.settings import (
    EVENT_SERIES_CREATION_ENABLED,
    MEETUP_CREATION_ENABLED,
    GlobalSettingsObject,
)
from eventyay.base.signals import register_global_settings
from eventyay.control.forms.global_settings import (
    GlobalSettingsForm,
    GlobalTicketingSettingsForm,
)


@pytest.fixture
def admin_user():
    return User.objects.create_user('admin@example.com', 'dummy', is_staff=True)


@pytest.fixture
def staff_client(client, admin_user):
    client.force_login(admin_user)
    admin_user.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    return client


@pytest.mark.django_db
class TestGlobalSettingsTabsAndSections:
    def test_settings_tab_order_in_form(self):
        form = GlobalSettingsForm()
        group_keys = [g[0] for g in form.field_groups]

        # Expected order of tabs
        expected_tabs = [
            'meta-data',
            'event-creation',
            'organizers',
            'localization',
            'email',
            'update-check',
            'maps',
            'etherpad',
            'voxbento',
            'hubspot',
        ]
        assert group_keys == expected_tabs

        # Payment Gateways and Cart should NOT be in GlobalSettingsForm
        assert 'payment_gateways' not in group_keys
        assert 'payment-gateways' not in group_keys
        assert 'cart' not in group_keys

    def test_settings_page_renders_expected_tabs_and_sections(self, staff_client):
        url = reverse('eventyay_admin:admin.global.settings')
        response = staff_client.get(url)
        assert response.status_code == 200
        content = response.content.decode('utf-8')

        # Check fieldset IDs for tabs
        assert 'id="tab-meta-data"' in content
        assert 'id="tab-event-creation"' in content
        assert 'id="tab-organizers"' in content
        assert 'id="tab-localization"' in content
        assert 'id="tab-email"' in content
        assert 'id="tab-update-check"' in content
        assert 'id="tab-maps"' in content
        assert 'id="tab-etherpad"' in content
        assert 'id="tab-voxbento"' in content
        assert 'id="tab-hubspot"' in content

        # Check Meta data content
        assert 'seo_homepage_title' in content
        assert 'seo_homepage_description' in content
        assert 'seo_social_image' in content

        # Check Event Creation and Organizers content
        assert 'Organizers' in content
        assert 'allow_all_users_create_organizer' in content
        assert 'allow_payment_users_create_organizer' in content
        assert 'event_series_creation_enabled' in content
        assert 'meetup_creation_enabled' in content

        # Check Update check tab content
        assert 'Update check results' in content
        assert 'update_check_perform' in content
        assert 'update_check_email' in content
        assert 'telemetry_enabled' in content

        # Payment Gateways and Cart must NOT be in Settings page
        assert 'id="tab-payment-gateways"' not in content
        assert 'id="tab-payment_gateways"' not in content
        assert 'id="tab-cart"' not in content

    def test_settings_save_behavior(self, staff_client):
        url = reverse('eventyay_admin:admin.global.settings')
        post_data = {
            'region': 'DE',
            'mail_from': 'noreply@example.com',
            'email_vendor': 'smtp',
            'smtp_host': 'smtp.example.com',
            'smtp_port': '587',
            'allow_all_users_create_organizer': 'on',
            'allow_payment_users_create_organizer': 'on',
            'event_series_creation_enabled': 'on',
            'meetup_creation_enabled': 'on',
            'seo_homepage_title': 'My Platform Title',
            'seo_homepage_description': 'My Platform Description',
            'update_check_perform': 'on',
            'update_check_email': 'updates@example.com',
            'telemetry_enabled': 'on',
        }
        response = staff_client.post(url, post_data)
        assert response.status_code == 302, (response.context['form'].errors if response.context and 'form' in response.context else response.content)
        assert response['Location'] == reverse('eventyay_admin:admin.global.settings')

        gs = GlobalSettingsObject()
        assert gs.settings.get('seo_homepage_title') == 'My Platform Title'
        assert gs.settings.get('seo_homepage_description') == 'My Platform Description'
        assert gs.settings.get('allow_all_users_create_organizer', as_type=bool) is True
        assert gs.settings.get('allow_payment_users_create_organizer', as_type=bool) is True
        assert gs.settings.get(EVENT_SERIES_CREATION_ENABLED, as_type=bool) is True
        assert gs.settings.get(MEETUP_CREATION_ENABLED, as_type=bool) is True
        assert gs.settings.get('update_check_perform', as_type=bool) is True
        assert gs.settings.get('update_check_email') == 'updates@example.com'
        assert gs.settings.get('telemetry_enabled', as_type=bool) is True

    @patch('eventyay.control.views.global_settings.update_check.apply')
    def test_update_check_trigger_in_settings(self, mock_update_check, staff_client):
        url = reverse('eventyay_admin:admin.global.settings')
        response = staff_client.post(url, {'trigger': '1'})
        assert response.status_code == 302
        assert response['Location'] == f"{reverse('eventyay_admin:admin.global.settings')}#tab-update-check"
        mock_update_check.assert_called_once()

    def test_social_image_save_failure_preserves_existing_image(self):
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        from django.core.files.uploadedfile import SimpleUploadedFile

        existing_path = default_storage.save('pub/global/existing_image.png', ContentFile(b'existing content'))
        try:
            gs = GlobalSettingsObject()
            gs.settings.set('seo_social_image', f'file://{existing_path}')

            uploaded_file = SimpleUploadedFile('new_image.png', b'new content', content_type='image/png')
            form_data = {
                'region': 'DE',
                'mail_from': 'admin@example.com',
                'email_vendor': 'smtp',
                'smtp_host': 'smtp.example.com',
                'smtp_port': '587',
            }
            form_files = {
                'seo_social_image': uploaded_file,
            }
            form = GlobalSettingsForm(data=form_data, files=form_files)
            assert form.is_valid(), form.errors

            with patch('django.core.files.storage.default_storage.save', side_effect=OSError('Disk full')), \
                 patch('django.core.files.storage.default_storage.delete') as mock_delete:
                form.save()
                mock_delete.assert_not_called()

            assert default_storage.exists(existing_path)
            assert gs.settings.get('seo_social_image', as_type=str) == f'file://{existing_path}'
        finally:
            if default_storage.exists(existing_path):
                default_storage.delete(existing_path)


@pytest.mark.django_db
class TestGlobalTicketingSettings:
    def test_ticketing_permissions(self, client):
        url = reverse('eventyay_admin:admin.global.ticketing')
        # Anonymous redirected
        resp_anon = client.get(url)
        assert resp_anon.status_code == 302
        assert 'login' in resp_anon['Location']

        # Non-staff forbidden
        non_staff = User.objects.create_user('regular@example.com', 'dummy')
        client.force_login(non_staff)
        resp_non_staff = client.get(url)
        assert resp_non_staff.status_code == 403

    def test_ticketing_page_renders_payment_gateways_and_cart(self, staff_client):
        url = reverse('eventyay_admin:admin.global.ticketing')
        response = staff_client.get(url)
        assert response.status_code == 200
        content = response.content.decode('utf-8')

        # Page title and tabs
        assert '<h1>Ticketing Settings</h1>' in content
        assert 'id="tab-payment-gateways"' in content
        assert 'id="tab-cart"' in content

        # Payment gateway providers
        assert 'Stripe — Ticket Payments' in content
        assert 'PayPal — Ticket Payments' in content
        assert 'payment_stripe_connect_client_id' in content
        assert 'payment_stripe_connect_publishable_key' in content
        assert 'payment_stripe_connect_secret_key' in content
        assert 'payment_paypal_connect_client_id' in content

        # Cart fields
        assert 'reservation_time' in content
        assert 'max_products_per_order' in content

        # Business organizer billing fields must NOT be in ticketing
        assert 'payment_stripe_publishable_key' not in content
        assert 'ticket_fee_percentage' not in content
        assert 'billing_validation' not in content

    def test_ticketing_settings_save_behavior(self, staff_client):
        url = reverse('eventyay_admin:admin.global.ticketing')
        post_data = {
            'payment_stripe_connect_client_id': 'ca_test_client_id',
            'payment_stripe_connect_publishable_key': 'pk_live_ticket_stripe_key',
            'payment_stripe_connect_secret_key': 'sk_live_ticket_stripe_key',
            'payment_stripe_connect_app_fee_percent': '2.50',
            'payment_paypal_connect_client_id': 'paypal_client_123',
            'reservation_time': '45',
            'max_products_per_order': '10',
        }
        response = staff_client.post(url, post_data)
        assert response.status_code == 302
        assert response['Location'] == reverse('eventyay_admin:admin.global.ticketing')

        gs = GlobalSettingsObject()
        assert gs.settings.get('payment_stripe_connect_client_id') == 'ca_test_client_id'
        assert gs.settings.get('payment_stripe_connect_publishable_key') == 'pk_live_ticket_stripe_key'
        assert gs.settings.get('payment_stripe_connect_app_fee_percent', as_type=Decimal) == Decimal('2.50')
        assert gs.settings.get('payment_paypal_connect_client_id') == 'paypal_client_123'
        assert gs.settings.get('reservation_time', as_type=int) == 45
        assert gs.settings.get('max_products_per_order', as_type=int) == 10


@pytest.mark.django_db
class TestLegacyUrlsAndRedirects:
    def test_legacy_metadata_url_redirects_to_settings_tab(self, staff_client):
        url = reverse('eventyay_admin:admin.global.metadata')
        response = staff_client.get(url)
        assert response.status_code == 302
        assert response['Location'] == f"{reverse('eventyay_admin:admin.global.settings')}#tab-meta-data"

    def test_legacy_update_url_redirects_to_settings_tab(self, staff_client):
        url = reverse('eventyay_admin:admin.global.update')
        response = staff_client.get(url)
        assert response.status_code == 302
        assert response['Location'] == f"{reverse('eventyay_admin:admin.global.settings')}#tab-update-check"

    def test_legacy_update_url_post_trigger_executes_update_check_and_redirects(self, staff_client):
        url = reverse('eventyay_admin:admin.global.update')
        with patch('eventyay.control.views.global_settings.update_check.apply') as mock_apply:
            response = staff_client.post(url, {'trigger': '1'})
            assert response.status_code == 302
            assert response['Location'] == f"{reverse('eventyay_admin:admin.global.settings')}#tab-update-check"
            mock_apply.assert_called_once()

    def test_global_settings_query_tab_redirects_for_ticketing(self, staff_client):
        url = reverse('eventyay_admin:admin.global.settings')

        for tab in ('payment_gateways', 'payment-gateways', 'payment', 'gateways'):
            response = staff_client.get(f'{url}?tab={tab}')
            assert response.status_code == 302
            assert response['Location'] == f"{reverse('eventyay_admin:admin.global.ticketing')}#tab-payment-gateways"

        response_cart = staff_client.get(f'{url}?tab=cart')
        assert response_cart.status_code == 302
        assert response_cart['Location'] == f"{reverse('eventyay_admin:admin.global.ticketing')}#tab-cart"

    def test_global_settings_query_tab_redirects_for_metadata_and_update(self, staff_client):
        url = reverse('eventyay_admin:admin.global.settings')

        for tab in ('meta_data', 'metadata', 'meta-data'):
            response = staff_client.get(f'{url}?tab={tab}')
            assert response.status_code == 302
            assert response['Location'] == f"{reverse('eventyay_admin:admin.global.settings')}#tab-meta-data"

        for tab in ('update_check', 'update', 'update-check'):
            response = staff_client.get(f'{url}?tab={tab}')
            assert response.status_code == 302
            assert response['Location'] == f"{reverse('eventyay_admin:admin.global.settings')}#tab-update-check"


@pytest.mark.django_db
class TestPluginProvidedPaymentSettingsRegression:
    def test_plugin_provided_payment_field_collected_in_ticketing_form_and_saved(self):
        def custom_payment_receiver(sender, **kwargs):
            return OrderedDict([
                ('payment_customplugin_api_key', dj_forms.CharField(label='Custom Plugin API Key', required=False)),
                ('customplugin_general_setting', dj_forms.CharField(label='General Plugin Setting', required=False)),
            ])

        register_global_settings.connect(custom_payment_receiver, dispatch_uid='test_custom_payment_receiver')
        try:
            # GlobalTicketingSettingsForm must collect payment_customplugin_api_key
            ticketing_form = GlobalTicketingSettingsForm()
            assert 'payment_customplugin_api_key' in ticketing_form.fields
            assert 'customplugin_general_setting' not in ticketing_form.fields

            payment_group = next(g for g in ticketing_form.field_groups if g[0] == 'payment-gateways')
            assert 'payment_customplugin_api_key' in payment_group[2]

            # GlobalSettingsForm must collect customplugin_general_setting and NOT payment_customplugin_api_key
            settings_form = GlobalSettingsForm()
            assert 'customplugin_general_setting' in settings_form.fields
            assert 'payment_customplugin_api_key' not in settings_form.fields

            # Verify saving via GlobalTicketingSettingsForm persists the value
            post_data = {
                'payment_customplugin_api_key': 'test_secret_token_123',
                'reservation_time': '30',
                'max_products_per_order': '5',
            }
            bound_form = GlobalTicketingSettingsForm(data=post_data)
            assert bound_form.is_valid(), bound_form.errors
            bound_form.save()

            gs = GlobalSettingsObject()
            assert gs.settings.get('payment_customplugin_api_key') == 'test_secret_token_123'
        finally:
            register_global_settings.disconnect(dispatch_uid='test_custom_payment_receiver')
