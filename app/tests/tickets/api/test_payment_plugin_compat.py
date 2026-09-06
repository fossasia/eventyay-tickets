import importlib
import importlib.util

import pytest
from django.apps import apps
from django.urls import reverse

from eventyay.config.urls import plugin_webhook_compat_paths


def test_missing_payment_plugin_does_not_register_webhook_aliases():
    assert plugin_webhook_compat_paths('definitely_not_installed_eventyay_plugin', '_x') == []


def test_broken_payment_plugin_view_does_not_raise(monkeypatch):
    def boom(name):
        raise AttributeError('missing webhook')

    monkeypatch.setattr('eventyay.config.urls.importlib.import_module', boom)
    assert plugin_webhook_compat_paths('eventyay_paypal', '_paypal') == []
    assert plugin_webhook_compat_paths('eventyay_stripe', '_stripe') == []


@pytest.mark.django_db
def test_installed_plugin_url_modules_still_import():
    failures = []
    for app in apps.get_app_configs():
        if not hasattr(app, 'EventyayPluginMeta'):
            continue
        module_name = f'{app.name}.urls'
        if importlib.util.find_spec(module_name) is None:
            continue
        try:
            importlib.import_module(module_name)
        except (ImportError, AttributeError, TypeError) as exc:
            failures.append(f'{app.name}: {exc}')
    assert failures == []


@pytest.mark.django_db
def test_stripe_and_paypal_webhook_aliases_still_reverse():
    assert reverse('stripe-payment-webhook-compat') == '/_stripe/webhook'
    assert reverse('stripe-payment-webhook-tickets-compat') == '/tickets/_stripe/webhook'
    assert reverse('paypal-payment-webhook-compat') == '/_paypal/webhook'
    assert reverse('paypal-payment-webhook-tickets-compat') == '/tickets/_paypal/webhook'


@pytest.mark.django_db
def test_payment_plugin_canonical_routes_still_reverse():
    assert reverse('plugins:eventyay_stripe:webhook') == '/_stripe/webhook/'
    assert reverse('plugins:eventyay_stripe:oauth.return') == '/_stripe/oauth_return/'
    assert reverse('plugins:eventyay_paypal:webhook') == '/_paypal/webhook/'
    assert reverse('plugins:eventyay_paypal:oauth.return') == '/_paypal/oauth_return/'


@pytest.mark.django_db
def test_other_installed_plugins_keep_named_routes():
    routes = [
        ('eventyay.plugins.badges', 'plugins:badges:index', {'organizer': 'dummy-org', 'event': 'dummy-event'}),
        (
            'eventyay.plugins.banktransfer',
            'plugins:banktransfer:import',
            {'organizer': 'dummy-org', 'event': 'dummy-event'},
        ),
        (
            'eventyay_bitpay',
            'plugins:eventyay_bitpay:auth.start',
            {'organizer': 'dummy-org', 'event': 'dummy-event'},
        ),
        ('eventyay_stripe', 'plugins:eventyay_stripe:oauth.return', None),
        ('eventyay_paypal', 'plugins:eventyay_paypal:oauth.return', None),
    ]
    for app_name, url_name, kwargs in routes:
        if not apps.is_installed(app_name):
            continue
        reverse(url_name, kwargs=kwargs)
