import copy
import json

from django.utils.translation import gettext, ugettext_lazy as _
from i18nfield.strings import LazyI18nString
from i18nfield.utils import I18nJSONEncoder

from pretalx.common.utils import language

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
        },
        {
            "title": _("That's it about your submission! We now just need a way to contact you."),
            "text": _("To create your submission, you need an account on this page. This not only gives us a way to contact you, it also gives you the possibility to edit your submission or to view its current state."),
            "icon": "user-circle-o",
            "icon_label": _("Account"),
            "identifier": "user",
        },
        {
            "title": _("Tell us more!"),
            "text": _("Before we can save your submission, we have some more questions for you."),
            "icon": "questions-circle-o",
            "icon_label": _("Questions"),
            "identifier": "questions",
        },
        {
            "title": _("Tell us something about yourself!"),
            "text": _("This information will be publicly displayed next to your talk - you can always edit for as long as submissions are still open."),
            "icon": "address-card-o",
            "icon_label": _("Profile"),
            "identifier": "profile",
        },
    ]
}


def i18n_string(data, locales):
    with language("en"):
        if hasattr(data, "_proxy____prepared"):
            data = str(data)
        if isinstance(data, str):
            data = {"en": str(data)}
        if not isinstance(data, dict):
            data = {"en": ""}
        english = data.get("en", "")

    for locale in locales:
        if locale not in data:
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
        for step in data["steps"]:
            for key in ("title", "text", "icon_label"):
                step[key] = i18n_string(step.get(key), locales)
        self.steps = data["steps"]
        self.steps_dict = {
            step.get('identifier', str(index)): step
            for index, step in enumerate(self.steps)
        }

    def all_data(self):
        return {
            "event": self.event.slug,
            "steps": self.steps,
        }

    @staticmethod
    def data(self):
        """Returns the canonical CfPWorkflow data format.
        Each step contains a 'title', a 'text', an 'icon', an 'icon_label', and
        a 'fields' list.
        The login/register form has instead an 'identifier', which is 'auth'.

        All fields will have:
            - A field_source, one of submission, user, profile, or question
            - For the types submission, user, and profile: a field_name
            - For the question type: a question_pk
            - The keys help_text and required"""
        return json.dumps(self.all_data(), cls=I18nJSONEncoder)

    def to_json(self):
        return self.data(self)

    def json_safe_data(self):
        return json.loads(self.to_json())

    def save(self):
        self.event.settings.cfp_workflow = self.to_json()
