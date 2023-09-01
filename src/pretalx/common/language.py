from django.conf import settings
from django.utils.translation import get_language

LANGUAGE_CODES_MAPPING = {
    language.lower(): language for language in settings.LANGUAGES_INFORMATION
}


def get_language_information(lang: str):
    lang_key = LANGUAGE_CODES_MAPPING[lang.lower()]
    information = settings.LANGUAGES_INFORMATION[lang_key]
    information["code"] = lang
    return information


def get_current_language_information():
    language_code = get_language()
    return get_language_information(language_code)
