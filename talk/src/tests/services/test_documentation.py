import configparser
import importlib
from contextlib import suppress
from pathlib import Path

import pytest
from django.conf import settings
from django.dispatch import Signal

here = Path(__file__).parent
doc_dir = here / "../../../doc"
base_dir = here / "../../pretalx"

plugin_docs = (doc_dir / "developer/plugins/general.rst").read_text()
command_docs = (doc_dir / "administrator/commands.rst").read_text()


def test_documentation_includes_config_options():
    doc_text = (doc_dir / "administrator/configure.rst").read_text()
    config = configparser.RawConfigParser()
    config = config.read(here / "../../pretalx.example.cfg")

    for category in config:
        for key in category:
            assert key in doc_text


@pytest.mark.parametrize("app", settings.LOCAL_APPS)
def test_documentation_includes_signals(app):
    with suppress(ImportError):
        module = importlib.import_module(app + ".signals")
        for key in dir(module):
            attrib = getattr(module, key)
            if isinstance(attrib, Signal):
                assert key in plugin_docs


@pytest.mark.parametrize("app", settings.LOCAL_APPS)
def test_documentation_includes_management_commands(app):
    # devserver is not relevant for administrators, and spectacular is a
    # third-party command for API doc generation that we only have as a
    # local command in order to wrap it in scopes_disabled()
    excluded_commands = ("__init__.py", "devserver.py", "spectacular.py")
    with suppress(ImportError):
        importlib.import_module(app + ".management.commands")
        path = base_dir / app.partition(".")[-1] / "management/commands"
        for python_file in path.glob("*.py"):
            file_name = python_file.name
            if file_name not in excluded_commands:
                assert f"``{file_name[:-3]}``" in command_docs
