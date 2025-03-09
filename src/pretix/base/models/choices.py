from django.db import models
from django.utils.translation import gettext_lazy as _


class PriceModeChoices(models.TextChoices):
    NONE = "none", _("No effect")
    SET = "set", _("Set product price to")
    SUBTRACT = "subtract", _("Subtract from product price")
    PERCENT = "percent", _("Reduce product price by (%)")
