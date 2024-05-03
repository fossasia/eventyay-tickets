import os
from collections.abc import Sequence
from importlib import import_module

from django.utils.translation import get_supported_language_variant
from django.utils.translation.trans_real import to_language

from statici18n.conf import settings


def get_mod_func(callback):
    """
    Converts 'django.views.news.stories.story_detail' to
    ('django.views.news.stories', 'story_detail')
    """
    try:
        dot = callback.rindex(".")
    except ValueError:
        return callback, ""
    return callback[:dot], callback[dot + 1:]


def get_filename(*args, **kwargs):
    try:
        mod_name, func_name = get_mod_func(settings.STATICI18N_FILENAME_FUNCTION)
        _filename_func = getattr(import_module(mod_name), func_name)
    except (AttributeError, ImportError) as e:
        raise ImportError(
            "Couldn't import filename function %s: %s"
            % (settings.STATICI18N_FILENAME_FUNCTION, e)
        )
    return _filename_func(*args, **kwargs)


def default_filename(locale, domain, output_format="js"):
    language_code = get_supported_language_variant(locale)
    return os.path.join(language_code, "%s.%s" % (domain, output_format))


def legacy_filename(locale, domain, output_format="js"):
    return os.path.join(to_language(locale), "%s.%s" % (domain, output_format))


def get_packages(packages):
    if packages == "django.conf":
        return None

    if isinstance(packages, str):
        return packages

    if isinstance(packages, Sequence):
        return "+".join(packages)
