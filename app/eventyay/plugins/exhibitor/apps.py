import logging
from django.apps import AppConfig
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from eventyay import __version__ as version

logger = logging.getLogger(__name__)


class ExhibitorApp(AppConfig):
    name = 'eventyay.plugins.exhibitor'
    verbose_name = _('Exhibitor Management')

    class EventyayPluginMeta:
        name = _('Exhibitor Management')
        category = 'FEATURE'
        featured = True
        version = version
        description = _(
            'Comprehensive exhibitor management system with lead scanning, '
            'booth assignments, and integration with tickets, talks, and video components.'
        )
        author = 'eventyay Team'
        visible = True
        restricted = False

    def ready(self):
        """Initialize the plugin when Django starts."""
        try:
            from . import signals  # NOQA
            logger.info("Exhibitor plugin signals loaded successfully")
        except ImportError as e:
            logger.warning(f"Could not load exhibitor plugin signals: {e}")

        try:
            from .templatetags import exhibitor_tags  # NOQA
            logger.info("Exhibitor plugin template tags loaded successfully")
        except ImportError as e:
            logger.warning(f"Could not load exhibitor plugin template tags: {e}")

    @cached_property
    def compatibility_warnings(self):
        """Check for compatibility issues and return warnings."""
        errs = []
        
        try:
            import qrcode  # NOQA
        except ImportError:
            errs.append(_(
                "Install the python package 'qrcode' for QR code generation capabilities."
            ))
        
        try:
            from PIL import Image  # NOQA
        except ImportError:
            errs.append(_(
                "Install the python package 'Pillow' for image processing capabilities."
            ))
        
        return errs


default_app_config = 'eventyay.plugins.exhibitor.ExhibitorApp'