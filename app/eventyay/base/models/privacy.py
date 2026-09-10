from django.core.validators import URLValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class ConsentCategory(models.TextChoices):
    """
    Consent categories offered by the built-in consent manager.

    ``NECESSARY`` is special: services in this category are always active and
    cannot be switched off by the visitor, so it must never be rendered as an
    opt-in toggle.
    """

    NECESSARY = 'necessary', _('Strictly necessary')
    FUNCTIONAL = 'functional', _('Functional')
    ANALYTICS = 'analytics', _('Analytics')
    MARKETING = 'marketing', _('Marketing')
    EMBED = 'embed', _('Embedded content')

    @classmethod
    def optional(cls):
        """Categories the visitor may accept or reject."""
        return [c for c in cls if c != cls.NECESSARY]


def enabled_consent_categories(settings):
    """
    Optional categories an administrator has switched on.

    Shared by the frontend config builder and the admin overview so both agree
    on which categories are actually live.
    """
    return [
        category.value
        for category in ConsentCategory.optional()
        if settings.get(f'privacy_category_{category.value}_enabled', as_type=bool)
    ]


class ConsentProvider(models.TextChoices):
    DISABLED = 'disabled', _('Disabled')
    KLARO = 'klaro', _('Built-in Eventyay consent using Klaro')
    EXTERNAL = 'external', _('External CMP script')


class ThirdPartyService(models.Model):
    """
    Admin-managed registry of third-party services and the consent category
    each one belongs to.

    The registry is what the frontend consent layer is built from: every
    optional service listed here is blocked until its category is accepted.
    """

    name = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name=_('Service identifier'),
        help_text=_('Short machine name, e.g. "google-analytics". Used to match blocked scripts.'),
    )
    title = models.CharField(max_length=200, verbose_name=_('Display name'))
    provider = models.CharField(max_length=200, blank=True, verbose_name=_('Provider'))
    purpose = models.TextField(blank=True, verbose_name=_('Description / purpose'))
    category = models.CharField(
        max_length=20,
        choices=ConsentCategory.choices,
        blank=True,
        default='',
        verbose_name=_('Consent category'),
    )
    enabled = models.BooleanField(default=True, verbose_name=_('Enabled'))
    privacy_policy_url = models.CharField(
        max_length=500,
        blank=True,
        validators=[URLValidator()],
        verbose_name=_('Privacy policy URL'),
    )
    cookie_names = models.TextField(
        blank=True,
        verbose_name=_('Cookie names'),
        help_text=_('One cookie name per line.'),
    )

    class Meta:
        ordering = ('category', 'title')
        verbose_name = _('Third-party service')
        verbose_name_plural = _('Third-party services')

    def __str__(self):
        return self.title

    @property
    def required(self):
        return self.category == ConsentCategory.NECESSARY

    @property
    def cookie_name_list(self):
        """``cookie_names`` as a list, one entry per non-empty line."""
        return [line.strip() for line in self.cookie_names.splitlines() if line.strip()]

    def serialize_public(self):
        """Shape expected by the Klaro ``services`` config array."""
        return {
            'name': self.name,
            'title': str(self.title),
            'purposes': [self.category],
            'required': self.required,
            'default': self.required,
            'description': str(self.purpose),
            # Klaro clears these when the visitor declines or withdraws consent.
            'cookies': self.cookie_name_list,
        }
