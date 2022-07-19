from django.db import models
from django.utils.translation import gettext_lazy as _


class VenuelessSettings(models.Model):
    event = models.OneToOneField(
        to="event.Event",
        on_delete=models.CASCADE,
        related_name="venueless_settings",
    )
    token = models.TextField(
        help_text=_(
            "Generate a token with the trait 'world:api' in the Config -> Token Generator menu in Venueless. Leave empty to leave unchanged."
        ),
        verbose_name=_("Venueless Token"),
        null=True,
        blank=True,  # for easier get_or_create
    )
    url = models.URLField(
        help_text=_("URL of your Venueless event"),
        verbose_name=_("Venueless URL"),
        null=True,
        blank=True,  # for easier get_or_create
    )
    last_push = models.DateTimeField(null=True, blank=True)
