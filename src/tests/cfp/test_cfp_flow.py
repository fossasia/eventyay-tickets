import json

import pytest
from django.http import HttpResponseNotAllowed
from django_scopes import scope
from i18nfield.strings import LazyI18nString

from pretalx.cfp.flow import BaseCfPStep, i18n_string


@pytest.mark.parametrize('data,locales,expected', (
    ('Submission', ['en'], {'en': 'Submission'}),
    ('Submission', ['en', 'de'], {'en': 'Submission', 'de': 'Submission'}),
    ('Submission', ['en', 'de', 'xx'], {'en': 'Submission', 'de': 'Submission', 'xx': 'Submission'}),
    ({'en': 'Submission'}, ['en'], {'en': 'Submission'}),
    ({'en': 'Submission'}, ['en', 'de'], {'en': 'Submission', 'de': 'Submission'}),
    ({'en': 'Submission', 'de': 'Submission'}, ['en'], {'en': 'Submission', 'de': 'Submission'}),
    ({'en': 'Submission', 'de': 'Submission'}, ['en', 'de'], {'en': 'Submission', 'de': 'Submission'}),
    ({'en': 'Submission', 'de': 'WRONG'}, ['en', 'de'], {'en': 'Submission', 'de': 'WRONG'}),
    (LazyI18nString({'en': 'Submission'}), ['en', 'de'], {'en': 'Submission'}),
    (1, ['en', 'de'], {'en': '', 'de': ''}),
))
def test_i18n_string(data, locales, expected):
    assert i18n_string(data, locales).data == expected


@pytest.mark.parametrize('data,expected', (
    (None, {"steps": {}}),
    ([], {"steps": {}}),
    ({"steps": {"info": {}}}, {"steps": {"info": {"fields": []}}}),
    ({"steps": {"info": {"icon": "foo"}}}, {"steps": {"info": {"fields": [], "icon": "foo"}}}),
    ({"steps": {"info": {"fields": []}}}, {"steps": {"info": {"fields": []}}}),
    ({"steps": {"info": {"fields": [], "text": "teeext"}}}, {"steps": {"info": {"fields": [], "text": {"en": "teeext"}}}}),
    ({"steps": {"info": {"fields": [{"widget": "w", "key": "k", "help_text": "bar"}]}}}, {"steps": {"info": {"fields": [{"key": "k", "help_text": {"en": "bar"}}]}}}),
    ({"steps": []}, {"steps": {}}),
    ({"steps": [{"identifier": "info"}]}, {"steps": {"info": {"fields": []}}}),

))
@pytest.mark.django_db
def test_cfp_flow(event, data, expected):
    with scope(event=event):
        assert event.settings.cfp_flow == ''
        event.cfp_flow.save_config(event.cfp_flow.get_config(data))
        assert json.loads(event.settings.cfp_flow) == expected
        assert event.cfp_flow.get_config_json()


def test_base_cfp_step_attributes():
    step = BaseCfPStep(None)
    assert step.priority == 100
    assert step.done(None) is None
    assert isinstance(step.get(None), HttpResponseNotAllowed)
    assert isinstance(step.post(None), HttpResponseNotAllowed)
