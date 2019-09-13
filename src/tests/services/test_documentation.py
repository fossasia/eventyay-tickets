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

with (doc_dir / "developer/plugins/general.rst").open() as doc_file:
    plugin_docs = doc_file.read()


with (doc_dir / "administrator/commands.rst").open() as doc_file:
    command_docs = doc_file.read()


def test_documentation_includes_config_options():
    with (doc_dir / "administrator/configure.rst").open() as doc_file:
        doc_text = doc_file.read()
    config = configparser.RawConfigParser()
    config = config.read(here / "../../pretalx.cfg")

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
    with suppress(ImportError):
        importlib.import_module(app + ".management.commands")
        path = base_dir / app.partition('.')[-1] / 'management/commands'
        for python_file in path.glob('*.py'):
            file_name = python_file.name
            if file_name not in ['__init__.py', 'makemigrations.py']:
                assert f'python -m pretalx {file_name[:-3]}``' in command_docs
