from django.db import models
from django.utils.translation import gettext_lazy as _

class Choices:
    """Helper class to make choices available as class variables.

    It exposes a list with valid choices and at the same time generate the
    choices tuples forthe model class.
    Usage:
        class MyChoices(Choices):
            ONE = 'one'
            TWO = 'dwa'
            valid_choices = [ONE, TWO]

        class MyModel(PretalxModel):
            variant = models.CharField(
                max_length=MyChoices.get_max_length(),
                choices=MyChoices.get_choices(),
            )
    """

    valid_choices = []

    @classmethod
    def get_choices(cls):
        return cls.valid_choices

    @classmethod
    def get_max_length(cls):
        return max(len(val) for val, _ in cls.valid_choices)


class PriceModeChoices(models.TextChoices):
    NONE = 'none', _('No effect')
    SET = 'set', _('Set product price to')
    SUBTRACT = 'subtract', _('Subtract from product price')
    PERCENT = 'percent', _('Reduce product price by (%)')
