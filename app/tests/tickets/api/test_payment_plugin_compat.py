import importlib
import importlib.util
import types

import pytest
from django.apps import apps
from django.urls import reverse

from eventyay.config.urls import plugin_webhook_compat_paths


def test_missing_payment_plugin_does_not_register_webhook_aliases():
    assert plugin_webhook_compat_paths('definitely_not_installed_eventyay_plugin', '_x') == []


def test_missing_plugin_dependency_is_not_swallowed(monkeypatch):
    def boom(name):
        raise ModuleNotFoundError('No module named requests', name='requests')

    monkeypatch.setattr('eventyay.config.urls.importlib.import_module', boom)
    with pytest.raises(ModuleNotFoundError):
        plugin_webhook_compat_paths('eventyay_paypal', '_paypal')


def test_broken_payment_plugin_view_is_not_swallowed(monkeypatch):
    monkeypatch.setattr(
        'eventyay.config.urls.importlib.import_module',
        lambda name: types.SimpleNamespace(),
    )
    with pytest.raises(AttributeError):
        plugin_webhook_compat_paths('eventyay_paypal', '_paypal')


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


def _reverse_installed_plugin_routes(routes):
    checked = 0
    for app_name, url_name, expected, kwargs in routes:
        if not apps.is_installed(app_name):
            continue
        if kwargs:
            assert reverse(url_name, kwargs=kwargs) == expected
        else:
            assert reverse(url_name) == expected
        checked += 1
    if checked == 0:
        pytest.skip('No payment plugins installed')


@pytest.mark.django_db
def test_stripe_and_paypal_webhook_aliases_still_reverse():
    _reverse_installed_plugin_routes(
        [
            ('eventyay_stripe', 'stripe-payment-webhook-compat', '/_stripe/webhook', None),
            ('eventyay_stripe', 'stripe-payment-webhook-tickets-compat', '/tickets/_stripe/webhook', None),
            ('eventyay_paypal', 'paypal-payment-webhook-compat', '/_paypal/webhook', None),
            ('eventyay_paypal', 'paypal-payment-webhook-tickets-compat', '/tickets/_paypal/webhook', None),
        ]
    )


@pytest.mark.django_db
def test_payment_plugin_canonical_routes_still_reverse():
    _reverse_installed_plugin_routes(
        [
            ('eventyay_stripe', 'plugins:eventyay_stripe:webhook', '/_stripe/webhook/', None),
            ('eventyay_stripe', 'plugins:eventyay_stripe:oauth.return', '/_stripe/oauth_return/', None),
            ('eventyay_paypal', 'plugins:eventyay_paypal:webhook', '/_paypal/webhook/', None),
            ('eventyay_paypal', 'plugins:eventyay_paypal:oauth.return', '/_paypal/oauth_return/', None),
        ]
    )


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
