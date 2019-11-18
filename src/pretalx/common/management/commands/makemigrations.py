from django.core.management.commands.makemigrations import Command  # noqa
from django.db import models

IGNORED_ATTRS = ['verbose_name', 'help_text', 'choices']
EXEMPT_FIELDS = ['CountryField']

original_deconstruct = models.Field.deconstruct


def new_deconstruct(self):
    """Patches makemigration's logic to ignore fields that are not of relevance
    to our database.

    This avoids unnecessary, annoying migrations whenever a frontend
    facing string is changed.
    """
    name, path, args, kwargs = original_deconstruct(self)
    if not any(field in path for field in EXEMPT_FIELDS):
        for attr in IGNORED_ATTRS:
            kwargs.pop(attr, None)
    return name, path, args, kwargs


models.Field.deconstruct = new_deconstruct
