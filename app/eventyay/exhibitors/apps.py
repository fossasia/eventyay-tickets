from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ExhibitorsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'eventyay.exhibitors'
    verbose_name = _('Exhibitors')
    
    def ready(self):
        """Import signals when the app is ready"""
        try:
            import eventyay.exhibitors.signals  # noqa F401
        except ImportError:
            pass