import json
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.test import RequestFactory

from eventyay.base.forms.auth import PasswordForgotForm, RegistrationForm
from eventyay.base.models import Organizer
from eventyay.base.services.turnstile import (
    TURNSTILE_ERROR_MESSAGE,
    TURNSTILE_MISCONFIGURED_MESSAGE,
    get_failed_login_count,
    get_turnstile_settings,
    is_turnstile_enabled_for_action,
    record_failed_login_attempt,
    reset_failed_login_attempts,
    test_turnstile_connection,
    verify_turnstile_token,
)
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.templatetags.turnstile_tags import (
    is_turnstile_active,
    turnstile_script,
    turnstile_widget,
)
from eventyay.control.forms.global_settings import GlobalSettingsForm
from eventyay.control.forms.organizer_forms.organizer_update_form import OrganizerUpdateForm
from eventyay.control.views.global_settings import GlobalSettingsTestTurnstileView
from eventyay.presale.views.contact import ContactOrganizerView

test_turnstile_connection.__test__ = False


@pytest.fixture(autouse=True)
def clean_cache_and_settings(settings):
    settings.CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'turnstile-testing-cache',
        }
    }
    cache.clear()
    gs = GlobalSettingsObject().settings
    # Reset Turnstile settings to default disabled state
    gs.set('anti_abuse_provider', 'disabled')
    gs.set('turnstile_site_key', '')
    gs.set('turnstile_secret_key', '')
    gs.set('turnstile_on_registration', False)
    gs.set('turnstile_login_mode', 'disabled')
    gs.set('turnstile_failed_login_threshold', 3)
    gs.set('turnstile_on_password_reset', False)
    gs.set('turnstile_on_organizer_create', False)
    gs.set('turnstile_on_contact', False)
    yield
    cache.clear()


@pytest.mark.django_db
class TestTurnstileService:
    def test_default_settings(self):
        settings = get_turnstile_settings()
        assert settings['provider'] == 'disabled'
        assert settings['enabled'] is False
        assert settings['site_key'] == ''
        assert settings['secret_key'] == ''
        assert settings['on_registration'] is False
        assert settings['login_mode'] == 'disabled'
        assert settings['failed_login_threshold'] == 3

    def test_is_turnstile_enabled_when_disabled(self):
        rf = RequestFactory()
        request = rf.get('/login')
        assert is_turnstile_enabled_for_action('login', request) is False
        assert is_turnstile_enabled_for_action('registration', request) is False
        assert is_turnstile_enabled_for_action('password_reset', request) is False

    def test_is_turnstile_enabled_for_registration(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', '1x00000000000000000000AA')
        gs.set('turnstile_secret_key', '1x0000000000000000000000000000000AA')
        gs.set('turnstile_on_registration', True)

        rf = RequestFactory()
        request = rf.get('/signup')
        assert is_turnstile_enabled_for_action('registration', request) is True
        assert is_turnstile_enabled_for_action('login', request) is False

    def test_is_turnstile_enabled_without_keys(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', '')
        gs.set('turnstile_secret_key', '')
        gs.set('turnstile_on_registration', True)

        rf = RequestFactory()
        request = rf.get('/signup')
        assert is_turnstile_enabled_for_action('registration', request) is True

    def test_is_turnstile_enabled_for_login_always(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', '1x00000000000000000000AA')
        gs.set('turnstile_secret_key', '1x0000000000000000000000000000000AA')
        gs.set('turnstile_login_mode', 'always')

        rf = RequestFactory()
        request = rf.get('/login')
        assert is_turnstile_enabled_for_action('login', request) is True

    def test_is_turnstile_enabled_for_login_failed_attempts_only(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', '1x00000000000000000000AA')
        gs.set('turnstile_secret_key', '1x0000000000000000000000000000000AA')
        gs.set('turnstile_login_mode', 'failed_attempts_only')
        gs.set('turnstile_failed_login_threshold', 3)

        rf = RequestFactory()
        request = rf.post('/login', REMOTE_ADDR='192.0.2.1')

        # 0 attempts -> False
        assert get_failed_login_count(request) == 0
        assert is_turnstile_enabled_for_action('login', request) is False

        # 1st and 2nd attempt -> False
        record_failed_login_attempt(request)
        assert get_failed_login_count(request) == 1
        assert is_turnstile_enabled_for_action('login', request) is False

        record_failed_login_attempt(request)
        assert get_failed_login_count(request) == 2
        assert is_turnstile_enabled_for_action('login', request) is False

        # 3rd attempt reaches threshold -> True
        record_failed_login_attempt(request)
        assert get_failed_login_count(request) == 3
        assert is_turnstile_enabled_for_action('login', request) is True

        # Successful login resets attempts
        reset_failed_login_attempts(request)
        assert get_failed_login_count(request) == 0
        assert is_turnstile_enabled_for_action('login', request) is False

    def test_verify_turnstile_token_missing_secret(self):
        valid, error = verify_turnstile_token('some-token')
        assert valid is False
        assert error == 'missing-secret'

    def test_verify_turnstile_token_missing_token(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_secret_key', 'secret-key')

        valid, error = verify_turnstile_token('')
        assert valid is False
        assert error == 'missing-input-response'

    @patch('urllib.request.urlopen')
    def test_verify_turnstile_token_non_dict_responses(self, mock_urlopen):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_secret_key', 'secret-key')

        for invalid_payload in [None, [], 'some string', 123, True]:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(invalid_payload).encode('utf-8')
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            valid, error = verify_turnstile_token('token', remote_ip='192.0.2.1')
            assert valid is False
            assert error == 'invalid-response'

    @patch('urllib.request.urlopen')
    def test_verify_turnstile_token_success(self, mock_urlopen):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_secret_key', 'secret-key')

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({'success': True}).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        valid, error = verify_turnstile_token('valid-token', remote_ip='192.0.2.1')
        assert valid is True
        assert error is None

    @patch('urllib.request.urlopen')
    def test_verify_turnstile_token_failure(self, mock_urlopen):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_secret_key', 'secret-key')

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            'success': False,
            'error-codes': ['invalid-input-response'],
        }).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        valid, error = verify_turnstile_token('invalid-token', remote_ip='192.0.2.1')
        assert valid is False
        assert error == 'invalid-input-response'


    @patch('urllib.request.urlopen')
    def test_verify_turnstile_token_action_mismatch(self, mock_urlopen):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_secret_key', 'secret-key')

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            'success': True,
            'action': 'login',
        }).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        valid, error = verify_turnstile_token(
            'token',
            remote_ip='192.0.2.1',
            expected_action='registration',
        )
        assert valid is False
        assert error == 'action-mismatch'

    @patch('urllib.request.urlopen')
    def test_verify_turnstile_token_action_missing(self, mock_urlopen):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_secret_key', 'secret-key')

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            'success': True,
        }).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        valid, error = verify_turnstile_token(
            'token',
            remote_ip='192.0.2.1',
            expected_action='registration',
        )
        assert valid is False
        assert error == 'action-mismatch'

    @patch('urllib.request.urlopen')
    def test_verify_turnstile_token_hostname_mismatch(self, mock_urlopen):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_secret_key', 'secret-key')

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            'success': True,
            'hostname': 'evil.com',
        }).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        valid, error = verify_turnstile_token(
            'token',
            remote_ip='192.0.2.1',
            expected_hostname='example.com',
        )
        assert valid is False
        assert error == 'hostname-mismatch'


@pytest.mark.django_db
class TestTurnstileForms:
    def test_registration_form_when_disabled(self):
        form = RegistrationForm(data={
            'email': 'user@example.com',
            'password': 'ValidPassword123!',
            'password_repeat': 'ValidPassword123!',
        })
        assert form.is_valid()

    def test_registration_form_missing_token_when_enabled(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', 'site-key')
        gs.set('turnstile_secret_key', 'secret-key')
        gs.set('turnstile_on_registration', True)

        form = RegistrationForm(data={
            'email': 'user@example.com',
            'password': 'ValidPassword123!',
            'password_repeat': 'ValidPassword123!',
        })
        assert not form.is_valid()
        assert str(TURNSTILE_ERROR_MESSAGE) in form.non_field_errors()

    def test_registration_form_misconfigured_keys(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', '')
        gs.set('turnstile_secret_key', '')
        gs.set('turnstile_on_registration', True)

        form = RegistrationForm(data={
            'email': 'user@example.com',
            'password': 'ValidPassword123!',
            'password_repeat': 'ValidPassword123!',
        })
        assert not form.is_valid()
        assert str(TURNSTILE_MISCONFIGURED_MESSAGE) in form.non_field_errors()

    @patch('urllib.request.urlopen')
    def test_registration_form_valid_token(self, mock_urlopen):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', 'site-key')
        gs.set('turnstile_secret_key', 'secret-key')
        gs.set('turnstile_on_registration', True)

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            'success': True,
            'action': 'registration',
        }).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        form = RegistrationForm(data={
            'email': 'user@example.com',
            'password': 'ValidPassword123!',
            'password_repeat': 'ValidPassword123!',
            'cf-turnstile-response': 'valid-test-token',
        })
        assert form.is_valid()

    def test_password_forgot_form_when_enabled(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', 'site-key')
        gs.set('turnstile_secret_key', 'secret-key')
        gs.set('turnstile_on_password_reset', True)

        form = PasswordForgotForm(data={'email': 'user@example.com'})
        assert not form.is_valid()
        assert str(TURNSTILE_ERROR_MESSAGE) in form.non_field_errors()

    def test_organizer_update_form_does_not_require_turnstile(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', 'site-key')
        gs.set('turnstile_secret_key', 'secret-key')
        gs.set('turnstile_on_organizer_create', True)

        org = Organizer.objects.create(name='Existing Org', slug='existing-org')
        # Existing organizer instance (has pk) should NOT fail on missing turnstile token
        form = OrganizerUpdateForm(data={'name': 'Existing Org Renamed', 'slug': 'existing-org'}, instance=org)
        assert form.is_valid()


@pytest.mark.django_db
class TestTurnstileTemplateTags:
    def test_tags_when_disabled(self):
        rf = RequestFactory()
        request = rf.get('/login')
        context = {'request': request}

        assert turnstile_widget(context, action='login') == ''
        assert turnstile_script(context, action='login') == ''
        assert is_turnstile_active(context, 'login') is False

    def test_tags_when_enabled(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', 'test-site-key-123')
        gs.set('turnstile_secret_key', 'test-secret-key-123')
        gs.set('turnstile_login_mode', 'always')

        rf = RequestFactory()
        request = rf.get('/login')
        context = {'request': request}

        widget_html = turnstile_widget(context, action='login')
        assert 'cf-turnstile' in widget_html
        assert 'data-sitekey="test-site-key-123"' in widget_html
        assert 'data-action="login"' in widget_html

        script_html = turnstile_script(context, action='login')
        assert 'challenges.cloudflare.com/turnstile/v0/api.js' in script_html
        assert is_turnstile_active(context, 'login') is True

    def test_tags_escape_malicious_site_key(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', '"><script>alert(1)</script>')
        gs.set('turnstile_secret_key', 'test-secret-key-123')
        gs.set('turnstile_login_mode', 'always')

        rf = RequestFactory()
        request = rf.get('/login')
        context = {'request': request}

        widget_html = str(turnstile_widget(context, action='login'))
        assert '<script>alert(1)</script>' not in widget_html
        assert '&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;' in widget_html


@pytest.mark.django_db
class TestGlobalSettingsForm:
    def test_global_settings_turnstile_keys_marked_required(self):
        form = GlobalSettingsForm()
        assert getattr(form.fields['turnstile_site_key'], '_required', False) is True
        assert getattr(form.fields['turnstile_secret_key'], '_required', False) is True

    def test_global_settings_validation_turnstile_requires_keys(self):
        form = GlobalSettingsForm(data={
            'anti_abuse_provider': 'turnstile',
            'turnstile_site_key': '',
            'turnstile_secret_key': '',
            'email_vendor': 'smtp',
            'reservation_time': 30,
            'max_products_per_order': 0,
        })
        assert not form.is_valid()
        assert 'turnstile_site_key' in form.errors
        assert 'turnstile_secret_key' in form.errors


@pytest.mark.django_db
class TestSignupViewIntegration:
    def test_signup_page_loads_cleanly_when_turnstile_disabled(self, client):
        response = client.get('/accounts/signup/')
        assert response.status_code == 200
        assert 'cf-turnstile' not in response.content.decode('utf-8')

    def test_signup_page_loads_with_turnstile_widget_when_enabled(self, client):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', '1x00000000000000000000AA')
        gs.set('turnstile_secret_key', '1x0000000000000000000000000000000AA')
        gs.set('turnstile_on_registration', True)

        response = client.get('/accounts/signup/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'cf-turnstile' in content
        assert '1x00000000000000000000AA' in content


@pytest.mark.django_db
class TestContactOrganizerTurnstile:
    def test_contact_form_rejects_missing_token_when_enabled(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', 'site-key')
        gs.set('turnstile_secret_key', 'secret-key')
        gs.set('turnstile_on_contact', True)

        rf = RequestFactory()
        request = rf.post('/event/test-event/contact_organizer/', {'message': 'Hello organizer!'})
        user = MagicMock()
        user.is_authenticated = True
        user.email = 'sender@example.com'
        request.user = user
        event = MagicMock()
        event.show_contact_form.return_value = True
        event.contact_form_recipient_email.return_value = 'organizer@example.com'
        request.event = event

        view = ContactOrganizerView()
        response = view.post(request)
        assert response.status_code == 400
        assert json.loads(response.content)['success'] is False

    def test_contact_form_rate_limited_does_not_call_turnstile_verifier(self):
        gs = GlobalSettingsObject().settings
        gs.set('anti_abuse_provider', 'turnstile')
        gs.set('turnstile_site_key', 'site-key')
        gs.set('turnstile_secret_key', 'secret-key')
        gs.set('turnstile_on_contact', True)

        rf = RequestFactory()
        request = rf.post('/event/test-event/contact_organizer/', {
            'message': 'Hello organizer!',
            'cf-turnstile-response': 'some-token',
        })
        user = MagicMock()
        user.is_authenticated = True
        user.email = 'sender@example.com'
        request.user = user
        event = MagicMock()
        event.show_contact_form.return_value = True
        event.contact_form_recipient_email.return_value = 'organizer@example.com'
        request.event = event

        view = ContactOrganizerView()
        with patch.object(view, '_is_rate_limited', return_value=True), \
             patch('eventyay.presale.views.contact.verify_turnstile_token') as mock_verify:
            response = view.post(request)
            assert response.status_code == 429
            assert json.loads(response.content)['success'] is False
            assert not mock_verify.called


@pytest.mark.django_db
class TestTurnstileTestConnection:
    def test_test_turnstile_connection_missing_secret(self):
        success, message = test_turnstile_connection(secret_key='')
        assert success is False
        assert 'not configured' in message

    @patch('urllib.request.urlopen')
    def test_test_turnstile_connection_success_explicit_true(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({'success': True}).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        success, message = test_turnstile_connection(secret_key='valid-secret')
        assert success is True
        assert 'successful' in message

    @patch('urllib.request.urlopen')
    def test_test_turnstile_connection_success_probe_response(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            'success': False,
            'error-codes': ['invalid-input-response'],
        }).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        success, message = test_turnstile_connection(secret_key='valid-secret')
        assert success is True
        assert 'successful' in message

    @patch('urllib.request.urlopen')
    def test_test_turnstile_connection_invalid_secret(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            'success': False,
            'error-codes': ['invalid-input-secret'],
        }).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        success, message = test_turnstile_connection(secret_key='invalid-secret')
        assert success is False
        assert 'Invalid Turnstile secret key' in message

    @patch('urllib.request.urlopen')
    def test_test_turnstile_connection_network_error(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError('Connection refused')

        success, message = test_turnstile_connection(secret_key='some-secret')
        assert success is False
        assert 'Could not connect' in message

    @patch('urllib.request.urlopen')
    def test_test_turnstile_connection_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError('timed out')

        success, message = test_turnstile_connection(secret_key='some-secret')
        assert success is False
        assert 'timed out' in message


@pytest.mark.django_db
class TestGlobalSettingsTestTurnstileView:
    def test_view_missing_secret_redirects_with_error(self):
        rf = RequestFactory()
        request = rf.post('/control/global/settings/test-turnstile/', {})
        request.session = {}
        request.user = MagicMock(is_superuser=True, is_staff=True, has_active_staff_session=MagicMock(return_value=True))

        view = GlobalSettingsTestTurnstileView()
        response = view.post(request)
        assert response.status_code == 302
        assert response.url.endswith('#tab-security')
        assert 'admin_test_turnstile_feedback' in request.session
        assert request.session['admin_test_turnstile_feedback']['level'] == 'error'

    @patch('eventyay.control.views.global_settings.test_turnstile_connection')
    def test_view_with_post_secret_success(self, mock_test_conn):
        mock_test_conn.return_value = (True, 'Connection successful!')

        rf = RequestFactory()
        request = rf.post('/control/global/settings/test-turnstile/', {
            'turnstile_secret_key': '0x4AAAAAAtestkey',
        })
        request.session = {}
        request.user = MagicMock(is_superuser=True, is_staff=True, has_active_staff_session=MagicMock(return_value=True))

        view = GlobalSettingsTestTurnstileView()
        response = view.post(request)
        assert response.status_code == 302
        assert response.url.endswith('#tab-security')
        assert request.session['admin_test_turnstile_feedback']['level'] == 'success'
        assert request.session['admin_test_turnstile_feedback']['message'] == 'Connection successful!'
        mock_test_conn.assert_called_once_with(secret_key='0x4AAAAAAtestkey')

    @patch('eventyay.control.views.global_settings.test_turnstile_connection')
    def test_view_uses_saved_secret(self, mock_test_conn):
        mock_test_conn.return_value = (True, 'Connection successful!')
        gs = GlobalSettingsObject().settings
        gs.set('turnstile_secret_key', 'saved-secret-key')

        rf = RequestFactory()
        request = rf.post('/control/global/settings/test-turnstile/', {})
        request.session = {}
        request.user = MagicMock(is_superuser=True, is_staff=True, has_active_staff_session=MagicMock(return_value=True))

        view = GlobalSettingsTestTurnstileView()
        response = view.post(request)
        assert response.status_code == 302
        assert response.url.endswith('#tab-security')
        assert request.session['admin_test_turnstile_feedback']['level'] == 'success'
        mock_test_conn.assert_called_once_with(secret_key='saved-secret-key')



