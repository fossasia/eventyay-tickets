import pytest
from django.conf import settings
from django.test import TestCase
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer
from eventyay.base.plugins import get_all_plugins
from eventyay.base.signals import register_ticket_outputs

plugins = get_all_plugins(include_inactive=True)


@pytest.mark.django_db
@pytest.mark.parametrize('plugin', plugins)
def test_metadata(plugin):
    assert hasattr(plugin, 'name')
    assert hasattr(plugin, 'version')


@pytest.mark.django_db
@pytest.mark.parametrize('plugin', plugins)
def test_plugin_installed(plugin):
    assert plugin.module in settings.INSTALLED_APPS


def test_hubspot_in_beta_plugins():
    from eventyay.base.plugins import BETA_PLUGINS

    assert 'hubspot' in BETA_PLUGINS


class PluginSignalTest(TestCase):
    """
    This test case tests the EventPluginSignal handler
    """

    def setUp(self):
        o = Organizer.objects.create(name='Dummy', slug='dummy')
        self.event = Event.objects.create(
            organizer=o,
            name='Dummy',
            slug='dummy',
            date_from=now(),
        )

    def test_no_plugins_active(self):
        self.event.plugins = ''
        self.event.save()
        responses = register_ticket_outputs.send(self.event)
        self.assertEqual(len(responses), 0)

    def test_one_plugin_active(self):
        self.event.plugins = 'tests.tickets.testdummy'
        self.event.save()
        payload = {'foo': 'bar'}
        responses = register_ticket_outputs.send(self.event, **payload)
        self.assertEqual(len(responses), 1)
        self.assertIn('tests.tickets.testdummy.signals', [r[0].__module__ for r in responses])
