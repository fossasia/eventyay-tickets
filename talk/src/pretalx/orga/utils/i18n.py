# Inspired by https://github.com/asaglimbeni/django-datetime-widget/blob/master/datetimewidget/widgets.py
# Copyright (c) 2013, Alfredo Saglimbeni (BSD license)
import re

from django.conf import settings
from django.utils import translation
from django.utils.formats import get_format

date_conversion_to_moment = {
    "%a": "ddd",
    "%A": "dddd",
    "%w": "d",
    "%d": "DD",
    "%b": "MMM",
    "%B": "MMMM",
    "%m": "MM",
    "%y": "YY",
    "%Y": "YYYY",
    "%H": "HH",
    "%I": "hh",
    "%p": "a",
    "%M": "mm",
    "%S": "ss",
    "%f": "SSSSSS",
    "%z": "ZZ",
    "%Z": "zz",
    "%j": "DDDD",
    "%U": "ww",  # fuzzy translation
    "%W": "WW",
    "%c": "",
    "%x": "",
    "%X": "",
}

moment_locales = {
    "af",
    "az",
    "bs",
    "de-at",
    "en-gb",
    "et",
    "fr-ch",
    "hi",
    "it",
    "ko",
    "me",
    "ms-my",
    "pa-in",
    "se",
    "sr",
    "th",
    "tzm-latn",
    "zh-hk",
    "ar",
    "be",
    "ca",
    "de",
    "en-ie",
    "eu",
    "fr",
    "hr",
    "ja",
    "ky",
    "mi",
    "my",
    "pl",
    "si",
    "ss",
    "tlh",
    "uk",
    "zh-tw",
    "ar-ly",
    "bg",
    "cs",
    "dv",
    "en-nz",
    "fa",
    "fy",
    "hu",
    "jv",
    "lb",
    "mk",
    "nb",
    "pt-br",
    "sk",
    "sv",
    "tl-ph",
    "uz",
    "ar-ma",
    "bn",
    "cv",
    "el",
    "eo",
    "fi",
    "gd",
    "hy-am",
    "ka",
    "lo",
    "ml",
    "ne",
    "pt",
    "sl",
    "sw",
    "tr",
    "vi",
    "ar-sa",
    "bo",
    "cy",
    "en-au",
    "es-do",
    "fo",
    "gl",
    "id",
    "kk",
    "lt",
    "mr",
    "nl",
    "ro",
    "sq",
    "ta",
    "tzl",
    "x-pseudo",
    "ar-tn",
    "br",
    "da",
    "en-ca",
    "es",
    "fr-ca",
    "he",
    "is",
    "km",
    "lv",
    "ms",
    "nn",
    "ru",
    "sr-cyrl",
    "te",
    "tzm",
    "zh-cn",
}

JS_REGEX = re.compile(r"(?<!\w)(" + "|".join(date_conversion_to_moment.keys()) + r")\b")


def get_javascript_format(format_name):
    format_value = get_format(format_name)[0]
    return JS_REGEX.sub(
        lambda regex: date_conversion_to_moment[regex.group()], format_value
    )


def get_moment_locale(locale=None):
    cur_lang = locale or translation.get_language()
    if cur_lang in moment_locales:
        return cur_lang
    if "-" in cur_lang or "_" in cur_lang:
        main = cur_lang.replace("_", "-").split("-")[0]
        if main in moment_locales:
            return main
    return settings.LANGUAGE_CODE
