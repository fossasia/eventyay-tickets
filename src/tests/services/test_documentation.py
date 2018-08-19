import configparser
import glob
import importlib
import os
from contextlib import suppress

import pytest
from django.conf import settings
from django.dispatch import Signal

here = os.path.dirname(__file__)
doc_dir = os.path.join(here, "../../../doc")
base_dir = os.path.join(here, "../../pretalx")

with open(os.path.join(doc_dir, "developer/plugins/general.rst"), "r") as doc_file:
    plugin_docs = doc_file.read()


with open(os.path.join(doc_dir, "administrator/commands.rst"), "r") as doc_file:
    command_docs = doc_file.read()


def test_documentation_includes_config_options():
    with open(os.path.join(doc_dir, "administrator/configure.rst"), "r") as doc_file:
        doc_text = doc_file.read()
    config = configparser.RawConfigParser()
    config = config.read(os.path.join(here, "../../pretalx.cfg"))

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
        path = os.path.join(base_dir, app, 'management/commands/*.py')
        for python_file in glob.glob(path):
            file_name = python_file.split('/')[-1]
            if file_name != '__init__.py':
                assert f'python -m pretalx {file_name[:-3]}``' in command_docs
