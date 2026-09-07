import pytest
from django import forms
from django.http import HttpResponseNotAllowed
from django_scopes import scope
from i18nfield.strings import LazyI18nString

from eventyay.cfp.forms.cfp import CfPFormMixin
from eventyay.cfp.flow import BaseCfPStep, FormFlowStep, i18n_string


@pytest.mark.parametrize(
    "data,locales,expected",
    (
        ("Submission", ["en"], {"en": "Submission"}),
        ("Submission", ["en", "de"], {"en": "Submission", "de": "Submission"}),
        (
            "Submission",
            ["en", "de", "xx"],
            {"en": "Submission", "de": "Submission", "xx": "Submission"},
        ),
        ({"en": "Submission"}, ["en"], {"en": "Submission"}),
        ({"en": "Submission"}, ["en", "de"], {"en": "Submission", "de": "Submission"}),
        (
            {"en": "Submission", "de": "Submission"},
            ["en"],
            {"en": "Submission", "de": "Submission"},
        ),
        (
            {"en": "Submission", "de": "Submission"},
            ["en", "de"],
            {"en": "Submission", "de": "Submission"},
        ),
        (
            {"en": "Submission", "de": "WRONG"},
            ["en", "de"],
            {"en": "Submission", "de": "WRONG"},
        ),
        (LazyI18nString({"en": "Submission"}), ["en", "de"], {"en": "Submission"}),
        (1, ["en", "de"], {"en": "", "de": ""}),
    ),
)
def test_i18n_string(data, locales, expected):
    assert i18n_string(data, locales).data == expected


@pytest.mark.parametrize(
    "data,expected",
    (
        (None, {"steps": {}}),
        ([], {"steps": {}}),
        ({"steps": {"info": {}}}, {"steps": {"info": {"fields": []}}}),
        (
            {"steps": {"info": {"icon": "foo"}}},
            {"steps": {"info": {"fields": [], "icon": "foo"}}},
        ),
        ({"steps": {"info": {"fields": []}}}, {"steps": {"info": {"fields": []}}}),
        (
            {"steps": {"info": {"fields": [], "text": "teeext"}}},
            {"steps": {"info": {"fields": [], "text": {"en": "teeext"}}}},
        ),
        (
            {
                "steps": {
                    "info": {
                        "fields": [{"widget": "w", "key": "k", "help_text": "bar"}]
                    }
                }
            },
            {"steps": {"info": {"fields": [{"key": "k", "help_text": {"en": "bar"}}]}}},
        ),
        ({"steps": []}, {"steps": {}}),
        ({"steps": [{"identifier": "info"}]}, {"steps": {"info": {"fields": []}}}),
    ),
)
@pytest.mark.django_db
def test_cfp_flow(event, data, expected):
    with scope(event=event):
        assert event.cfp.settings["flow"] == {}
        event.cfp_flow.save_config(event.cfp_flow.get_config(data))
        assert event.cfp.settings["flow"] == expected
        assert event.cfp_flow.get_config_json()


def test_base_cfp_step_attributes():
    step = BaseCfPStep(None)
    assert step.priority == 100
    assert step.done(None) is None
    assert isinstance(step.get(None), HttpResponseNotAllowed)
    assert isinstance(step.post(None), HttpResponseNotAllowed)

def test_form_flow_step_handles_none_file_content_type():
    class TestFormFlowStep(FormFlowStep):
        @property
        def identifier(self):
            return 'test'

    step = TestFormFlowStep(None)
    step.cfp_session = {
        'files': {
            'test': {
                'image': {
                    'name': 'test.png',
                    'tmp_name': 'test.png',
                    'content_type': None,
                }
            }
        }
    }

    assert step.get_form_initial() == {}


def test_cfp_form_mixin_scrubs_incomplete_errors_in_not_strict_mode():
    class PartialValueField(forms.MultiValueField):
        def __init__(self, *args, **kwargs):
            super().__init__(
                fields=(
                    forms.CharField(required=True),
                    forms.CharField(required=True),
                ),
                require_all_fields=False,
                *args,
                **kwargs,
            )

        def compress(self, data_list):
            return data_list

    class DraftSplitForm(CfPFormMixin, forms.Form):
        availability = PartialValueField(required=True)

    form = DraftSplitForm(
        data={
            'availability_0': '2026-05-26',
            'availability_1': '',
        },
        not_strict=True,
    )

    assert form.is_valid()
    assert not form.errors
