import copy
import json
from collections import OrderedDict

from django.utils.translation import gettext, ugettext_lazy as _
from i18nfield.strings import LazyI18nString
from i18nfield.utils import I18nJSONEncoder

from pretalx.common.utils import language
from pretalx.person.forms import SpeakerProfileForm, UserForm
from pretalx.submission.forms import InfoForm, QuestionsForm

MARKDOWN_SUPPORT = {
    "submission_abstract", "submission_description", "submission_notes", "profile_biography",
}

DEFAULT_CFP_STEPS = {
    "event": None,
    "steps": [
        {
            "title": _("Hey, nice to meet you!"),
            "text": _("We're glad that you want to contribute to our event with your submission. Let's get started, this won't take long."),
            "icon": "paper-plane",
            "icon_label": _("General"),
            "identifier": "info",
            "form_class": InfoForm,
        },
        {
            "title": _("Tell us more!"),
            "text": _("Before we can save your submission, we have some more questions for you."),
            "icon": "question-circle-o",
            "icon_label": _("Questions"),
            "identifier": "questions",
            "form_class": QuestionsForm,
        },
        {
            "title": _("That's it about your submission! We now just need a way to contact you."),
            "text": _("To create your submission, you need an account on this page. This not only gives us a way to contact you, it also gives you the possibility to edit your submission or to view its current state."),
            "icon": "user-circle-o",
            "icon_label": _("Account"),
            "identifier": "user",
            "form_class": UserForm,
        },
        {
            "title": _("Tell us something about yourself!"),
            "text": _("This information will be publicly displayed next to your talk - you can always edit for as long as submissions are still open."),
            "icon": "address-card-o",
            "icon_label": _("Profile"),
            "identifier": "profile",
            "form_class": SpeakerProfileForm,
        },
    ]
}


def i18n_string(data, locales):
    locales = copy.deepcopy(locales)
    with language("en"):
        if hasattr(data, "_proxy____prepared"):
            data = str(data)
        if isinstance(data, str):
            data = {"en": str(data)}
        if not isinstance(data, dict):
            data = {"en": ""}
        english = data.get("en", "")

    for locale in locales:
        if locale != 'en' and not data.get(locale):
            with language(locale):
                data[locale] = gettext(english)
    return LazyI18nString(data)


class CfPWorkflow:
    steps = []
    event = None

    def __init__(self, data, event):
        self.event = event
        if isinstance(data, str) and data:
            data = json.loads(data)
        elif not isinstance(data, dict):
            data = copy.deepcopy(DEFAULT_CFP_STEPS)
        locales = self.event.locales
        self.steps = data["steps"]
        self.steps_dict = {}
        for index, step in enumerate(self.steps):
            for key in ("title", "text", "icon_label"):
                step[key] = i18n_string(step.get(key), locales)
            for key in ("icon", ):
                step[key] = DEFAULT_CFP_STEPS["steps"][index][key]
            identifier = step.get("identifier", str(index))
            fields = {field.get("key"): field for field in step.get("fields", [])}
            if identifier != "user":
                step["fields"] = [
                    {
                        "widget": field.widget.__class__.__name__,
                        "key": key,
                        "label": i18n_string(field.label, locales),
                        "help_text": i18n_string(
                            fields.get(key, {}).get("help_text") or getattr(field, 'original_help_text', field.help_text),
                            locales,
                        ),
                        "full_help_text": field.help_text,
                        "required": field.required,
                    }
                    for key, field in DEFAULT_CFP_STEPS["steps"][index]["form_class"](event=event).fields.items()  # TODO we rely on ordering here
                ]
            self.steps_dict[identifier] = step

    def all_data(self, saving=False):
        steps = copy.deepcopy(self.steps)
        for step in steps:
            step.pop("form_class", None)
            if saving:
                if "fields" in step:
                    step["fields"] = [
                        {
                            "help_text": field["help_text"].data,
                            "key": field["key"],
                        } for field in step["fields"]
                    ]
                step.pop("icon", None)
        return {
            "event": self.event.slug,
            "steps": steps,
        }

    @staticmethod
    def data(self, saving=False):
        return json.dumps(self.all_data(saving=saving), cls=I18nJSONEncoder)

    def to_json(self, saving=False):
        return self.data(self, saving=saving)

    def json_safe_data(self):
        return json.loads(self.to_json())

    def save(self):
        self.event.settings.cfp_workflow = self.to_json(saving=True)

    def get_form_list(self):
        return OrderedDict([
            (
                step.get('identifier', str(index)),
                DEFAULT_CFP_STEPS["steps"][index]["form_class"]
            )
            for index, step in enumerate(self.steps)
        ])
