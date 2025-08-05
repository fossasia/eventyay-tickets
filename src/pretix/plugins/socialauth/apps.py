from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from pretix import __version__ as version


class SocialAuthApp(AppConfig):
    name = 'pretix.plugins.socialauth'
    verbose_name = _('SocialAuth')

    class PretixPluginMeta:
        name = _('SocialAuth')
        author = _('the pretix team')
        version = version
        featured = True
        description = _('This plugin allows you to login via social networks')
        visible = False

    def ready(self):
        """Register custom providers when the app is ready."""
        super().ready()
        from allauth.socialaccount import providers
        from .mediawiki_provider import MediaWikiProvider
        
        # Replace the default MediaWiki provider with our custom rate-limited one
        providers.registry.unregister('mediawiki')
        providers.registry.register(MediaWikiProvider)


default_app_config = 'pretix.plugins.socialauth.SocialAuthApp'
