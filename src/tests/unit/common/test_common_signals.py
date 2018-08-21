import pytest

from pretalx.common.signals import EventPluginSignal, _populate_app_cache
from tests.dummy_signals import footer_link_test, footer_link


@pytest.mark.django_db
def test_is_plugin_active(event):
    _populate_app_cache()
    assert EventPluginSignal._is_active(event, footer_link_test) is False
    event.plugins = 'tests'
    assert EventPluginSignal._is_active(event, footer_link_test) is True


@pytest.mark.django_db
def test_cant_call_signal_without_event(event):
    _populate_app_cache()
    with pytest.raises(Exception):
        footer_link.send('something')
    footer_link.send(event)
