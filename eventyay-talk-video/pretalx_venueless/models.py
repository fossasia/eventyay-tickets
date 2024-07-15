from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nTextField
from pretalx.common.text.phrases import phrases


class VenuelessSettings(models.Model):
    event = models.OneToOneField(
        to="event.Event",
        on_delete=models.CASCADE,
        related_name="venueless_settings",
    )
    token = models.TextField(
        help_text=_(
            "Generate a token with the trait 'world:api' in the Config -> Token Generator menu in Eventyay video. Leave empty to leave unchanged."
        ),
        verbose_name=_("Eventyay video Token"),
        null=True,
        blank=True,  # for easier get_or_create
    )
    url = models.URLField(
        help_text=_("URL of your Eventyay video event"),
        verbose_name=_("Eventyay video URL"),
        null=True,
        blank=True,  # for easier get_or_create
    )
    last_push = models.DateTimeField(null=True, blank=True)

    # settings required for join URLs
    show_join_link = models.BooleanField(
        help_text=_(
            "If you enable this feature, speakers will find a Eventyay video join button on their profile pages."
        ),
        verbose_name=_("Show join button"),
        default=False,
    )
    join_url = models.URLField(
        help_text=_("URL used for sign-up links"),
        verbose_name=_("Eventyay video URL"),
        null=True,
        blank=True,
    )
    secret = models.TextField(
        verbose_name=_("Eventyay video secret"),
        null=True,
        blank=True,
    )
    issuer = models.TextField(
        verbose_name=_("Eventyay video issuer"),
        null=True,
        blank=True,
    )
    audience = models.TextField(
        verbose_name=_("Eventyay video audience"),
        null=True,
        blank=True,
    )
    join_start = models.DateTimeField(
        verbose_name=_("Do not allow access before"), null=True, blank=True
    )
    join_text = I18nTextField(
        verbose_name=_("Introductory text"),
        help_text=phrases.base.use_markdown,
        null=True,
        blank=True,
    )

    @property
    def can_join(self):
        return self.show_join_link and (not self.join_start or self.join_start <= now())
