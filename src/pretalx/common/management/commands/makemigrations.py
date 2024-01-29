"""This command supersedes the Django-inbuilt makemigrations command.

It serves to create fewer migrations: Django, for technically very good reasons,
creates migrations for tiny changes, including many that have no bearing on the
actual database, like help_texts.

It makes sense for Django to do so, but since pretalx only supports a small set
of databases, and we can handle required changes as they appear, we can be fairly
certain that many changes will never impact our databases. Fewer migrations mean
less update headaches and a more readable git history, so that's what we are going
for, even though the code is somewhat hacky. Props for this improved version
to the pretix project.
"""

from django.core.management.commands.makemigrations import Command as Parent
from django.db import models
from django.db.migrations.operations import models as modelops
from django_countries.fields import CountryField

modelops.AlterModelOptions.ALTER_OPTION_KEYS.remove("verbose_name")
modelops.AlterModelOptions.ALTER_OPTION_KEYS.remove("verbose_name_plural")
modelops.AlterModelOptions.ALTER_OPTION_KEYS.remove("ordering")
modelops.AlterModelOptions.ALTER_OPTION_KEYS.remove("get_latest_by")
modelops.AlterModelOptions.ALTER_OPTION_KEYS.remove("default_manager_name")
modelops.AlterModelOptions.ALTER_OPTION_KEYS.remove("permissions")
modelops.AlterModelOptions.ALTER_OPTION_KEYS.remove("default_permissions")
IGNORED_ATTRS = [
    # (field type, attribute name, blacklist of field sub-types)
    (models.Field, "verbose_name", []),
    (models.Field, "help_text", []),
    (models.Field, "validators", []),
    (
        models.Field,
        "editable",
        [models.DateField, models.DateTimeField, models.DateField, models.BinaryField],
    ),
    (
        models.Field,
        "blank",
        [
            models.DateField,
            models.DateTimeField,
            models.AutoField,
            models.NullBooleanField,
            models.TimeField,
        ],
    ),
    (models.CharField, "choices", [CountryField]),
]

original_deconstruct = models.Field.deconstruct


def new_deconstruct(self):
    name, path, args, kwargs = original_deconstruct(self)
    for ftype, attr, blacklist in IGNORED_ATTRS:
        if isinstance(self, ftype) and not any(
            isinstance(self, ft) for ft in blacklist
        ):
            kwargs.pop(attr, None)
    return name, path, args, kwargs


models.Field.deconstruct = new_deconstruct


class Command(Parent):
    pass
