"""This command supersedes the Django-inbuilt makemessages command.

We do this to allow the easy management of translations by way of plugins.
The way GNU gettext handles path precedence, it will always create new
translation files for given languages in the pretalx root locales directory
instead of updating the already existing plugin locale directory.

This management command copies all plugin-provided languages to the core
locales directory, then moves them back once the translations have been
generated and cleans up empty directories.

This command also handles frontend translations.

Yes, it's hacky, but have you tried managing symlinks instead?
"""

import shutil
import subprocess
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

        # Create frontend translations
        base_path = locale_path.parent
        frontend_path = base_path / "frontend/schedule-editor"
        locales = [locale.name for locale in locale_path.iterdir() if locale.is_dir()]

        # env = os.environ.copy()
        # env["PRETALX_LOCALES"] = ",".join(locales)
        subprocess.run(
            "npm run i18n:extract", check=True, shell=True, cwd=frontend_path
        )
        # We only need one file, as it's empty anyway
        # (and we don't use numbers or other fancy features.)
        subprocess.run(
            "npm run i18n:convert2gettext", check=True, shell=True, cwd=frontend_path
        )

        # Now merge the js file with the django file in each language
        for locale in locales:
            command = f"msgcat -o locale/{locale}/LC_MESSAGES/django.po --use-first locale/{locale}/LC_MESSAGES/django.po frontend/schedule-editor/locales/en/translation.po"
            subprocess.run(command, check=True, shell=True, cwd=base_path)
