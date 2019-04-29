from django.core.management.commands.makemigrations import Command
from django.db import models

IGNORED_ATTRS = ['verbose_name', 'help_text', 'choices']

original_deconstruct = models.Field.deconstruct


def new_deconstruct(self):
    name, path, args, kwargs = original_deconstruct(self)
    for attr in IGNORED_ATTRS:
        kwargs.pop(attr, None)
    return name, path, args, kwargs

models.Field.deconstruct = new_deconstruct
