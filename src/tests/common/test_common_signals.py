import pytest
from tests.dummy_signals import footer_link, footer_link_test

from pretalx.common.signals import EventPluginSignal, _populate_app_cache


@pytest.mark.django_db
def test_is_plugin_active(event):
    _populate_app_cache()
    event.plugins = None
    assert EventPluginSignal._is_active(event, footer_link_test) is False, event.plugin_list
    event.plugins = 'tests'
    assert EventPluginSignal._is_active(event, footer_link_test) is True, event.plugin_list


@pytest.mark.django_db
def test_cant_call_signal_without_event(event):
    _populate_app_cache()
    with pytest.raises(Exception):
        footer_link.send('something', request='test')
    footer_link.send(event, request='test')
