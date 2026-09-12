import logging

from django.db import OperationalError, ProgrammingError, models
from django.utils.translation import gettext_lazy as _


logger = logging.getLogger(__name__)


class GlobalPluginConfig(models.Model):
    """
    Stores platform-level configuration for each plugin.

    Platform admins can control:
    - Whether a plugin is active on the platform at all.
    - Whether a plugin is enabled by default for newly created events.
    - Whether a plugin appears in the organiser/event plugin list.
    - What type of plugin it is (payment provider, system, external).
    - Whether the plugin is required and cannot be deactivated.
    """

    class PluginType(models.TextChoices):
        PAYMENT_PROVIDER = 'payment_provider', _('Payment provider')
        SYSTEM = 'system', _('System plugin')
        EXTERNAL = 'external', _('External plugin')

    module = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_('Plugin module'),
        help_text=_('The Python module path of the plugin.'),
    )
    plugin_type = models.CharField(
        max_length=32,
        choices=PluginType.choices,
        default=PluginType.EXTERNAL,
        verbose_name=_('Plugin type'),
        help_text=_('Classification of the plugin.'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Controls whether the plugin is available on the platform at all.'),
    )
    is_required = models.BooleanField(
        default=False,
        verbose_name=_('Required'),
        help_text=_('Required plugins cannot be deactivated.'),
    )
    enable_by_default = models.BooleanField(
        default=False,
        verbose_name=_('Enable by default'),
        help_text=_('Controls whether the plugin is automatically enabled for new events.'),
    )
    show_in_organizer_list = models.BooleanField(
        default=True,
        verbose_name=_('Show in organizer plugin list'),
        help_text=_('Controls whether the plugin appears in the organiser/event plugin settings.'),
    )
    configured_via = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name=_('Configured via'),
        help_text=_('Describes where this plugin is configured (e.g. payment_settings, platform).'),
    )

    class Meta:
        ordering = ('module',)
        verbose_name = _('Global plugin configuration')
        verbose_name_plural = _('Global plugin configurations')

    def __str__(self) -> str:
        return self.module

    @property
    def is_platform_plugin(self) -> bool:
        return self.plugin_type in (
            self.PluginType.PAYMENT_PROVIDER,
            self.PluginType.SYSTEM,
        )

    @property
    def is_organiser_toggleable(self) -> bool:
        return self.plugin_type == self.PluginType.EXTERNAL

    @property
    def can_show_in_organiser_plugin_list(self) -> bool:
        return self.plugin_type == self.PluginType.EXTERNAL

    @classmethod
    def get_config(cls, module: str) -> 'GlobalPluginConfig | None':
        """
        Returns the configuration for the given plugin module,
        creating a default entry if one does not exist.
        Returns None if the table is not yet migrated.
        """
        try:
            config, _created = cls.objects.get_or_create(
                module=module,
                defaults={
                    'is_active': True,
                    'enable_by_default': False,
                    'show_in_organizer_list': True,
                },
            )
            return config
        except (ProgrammingError, OperationalError):
            logger.debug('GlobalPluginConfig table not yet available')
            return None

    @classmethod
    def get_disabled_modules(cls) -> frozenset[str]:
        """
        Returns the set of plugin modules that have been globally disabled.
        Plugins without a config entry are considered active by default.
        """
        try:
            return frozenset(
                cls.objects.filter(is_active=False).values_list('module', flat=True)
            )
        except (ProgrammingError, OperationalError):
            logger.debug('GlobalPluginConfig table not yet available, skipping filter')
            return frozenset()

    @classmethod
    def get_default_enabled_modules(cls) -> list[str]:
        """
        Returns plugin modules that should be enabled by default for new events.
        """
        try:
            return list(
                cls.objects.filter(
                    is_active=True, enable_by_default=True
                ).values_list('module', flat=True)
            )
        except (ProgrammingError, OperationalError):
            logger.debug('GlobalPluginConfig table not yet available, skipping defaults')
            return []

    @classmethod
    def get_hidden_from_organizer_modules(cls) -> frozenset[str]:
        """
        Returns plugin modules that should not appear in organiser plugin lists.
        """
        try:
            return frozenset(
                cls.objects.filter(
                    models.Q(show_in_organizer_list=False)
                    | models.Q(plugin_type__in=[
                        cls.PluginType.PAYMENT_PROVIDER,
                        cls.PluginType.SYSTEM,
                    ])
                ).values_list('module', flat=True)
            )
        except (ProgrammingError, OperationalError):
            logger.debug('GlobalPluginConfig table not yet available, skipping filter')
            return frozenset()

    @classmethod
    def get_platform_managed_modules(cls) -> frozenset[str]:
        try:
            return frozenset(
                cls.objects.filter(
                    is_active=True,
                    is_required=True,
                ).values_list('module', flat=True)
            )
        except (ProgrammingError, OperationalError):
            logger.debug('GlobalPluginConfig table not yet available, skipping filter')
            return frozenset()
