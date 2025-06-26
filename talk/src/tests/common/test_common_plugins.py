import pytest

from pretalx.common.plugins import get_all_plugins
from tests.dummy_app import PluginApp


@pytest.mark.django_db
def test_get_all_plugins():
    assert PluginApp.PretalxPluginMeta in get_all_plugins(), get_all_plugins()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "event,expected", ((None, True), ("hidden", True), ("totally hidden", False))
)
def test_get_all_plugins_with_event(event, expected):
    assert (PluginApp.PretalxPluginMeta in get_all_plugins(event)) is expected
