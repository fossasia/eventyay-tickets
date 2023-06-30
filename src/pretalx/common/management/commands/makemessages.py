"""This command supersedes the Django-inbuilt makemessages command.

We do this to allow the easy management of translations by way of plugins.
The way GNU gettext handles path precedence, it will always create new
translation files for given languages in the pretalx root locales directory
instead of updating the already existing plugin locale directory.

This management command copies all plugin-provided languages to the core
locales directory, then moves them back once the translations have been
generated and cleans up empty directories.

Yes, it's hacky, but have you tried managing symlinks instead?
"""
import shutil
from importlib import import_module
from pathlib import Path

from django.conf import settings
from django.core.management.commands.makemessages import Command as Parent

from pretalx.common.signals import register_locales


def pathreplace(left, right):
    left.mkdir(parents=True, exist_ok=True)
    right.mkdir(parents=True, exist_ok=True)
    left.replace(right)


class Command(Parent):
    def handle(self, *args, **options):
        locales = {}
        for receiver, response in register_locales.send(sender=None):
            module = import_module(receiver.__module__.split(".")[0])
            path = Path(module.__path__[0])
            for locale in response:
                # if it's a tuple, use the first part
                if isinstance(locale, tuple):
                    locale = locale[0]
                if "-" in locale:
                    locale_parts = locale.split("-")
                    locale = (
                        locale_parts[0]
                        + "_"
                        + "_".join(part.capitalize() for part in locale_parts[1:])
                    )
                locales[locale] = path

        if not locales:
            super().handle(*args, **options)

        locale_path = Path(settings.LOCALE_PATHS[0])
        moves = []
        for locale, path in locales.items():
            translation_path = path / "locale" / locale
            translation_file = translation_path / "LC_MESSAGES/django.po"
            new_dir = locale_path / locale
            moves.append((translation_path, new_dir))

            if not translation_file.exists():
                print(f"{translation_file} does not exist, regenerating.")
                continue

            if new_dir.exists():
                shutil.rmtree(new_dir)
            translation_path.replace(new_dir)

        super().handle(*args, **options)

        for move in moves:
            pathreplace(move[1], move[0])
