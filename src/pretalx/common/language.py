from copy import copy

from django.conf import global_settings, settings
from django.utils.translation import get_language

LANGUAGE_CODES_MAPPING = {
    language.lower(): language for language in settings.LANGUAGES_INFORMATION
}
LANGUAGE_NAMES = dict(global_settings.LANGUAGES)
LANGUAGE_NAMES.update(
    (language["code"], language["natural_name"])
    for language in settings.LANGUAGES_INFORMATION.values()
)


def get_language_information(lang: str):
    lang_key = LANGUAGE_CODES_MAPPING[lang.lower()]
    information = copy(settings.LANGUAGES_INFORMATION[lang_key])
    information["code"] = lang
    return information


def get_current_language_information():
    language_code = get_language()
    return get_language_information(language_code)
