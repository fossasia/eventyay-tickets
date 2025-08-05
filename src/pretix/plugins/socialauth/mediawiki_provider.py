from django.utils.translation import gettext_lazy as _
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider
from pretix.base.i18n import LazyLocaleException


class MediaWikiRateLimitException(LazyLocaleException):
    """Exception for MediaWiki rate limit with user-friendly message."""
    
    def __init__(self, message=None):
        if message:
            super().__init__(message)
        else:
            super().__init__(
                _("MediaWiki server is busy now, please try again after a few minutes.")
            )


class MediaWikiProvider(OAuth2Provider):
    """Minimal MediaWiki OAuth2 provider following django-allauth patterns."""
    
    id = 'mediawiki'
    name = 'MediaWiki'
    # TODO: Add proper OAuth2Adapter class - currently missing oauth2_adapter_class
    # This is a critical flaw that prevents the provider from working
    
    def get_default_scope(self):
        return ['identify']
    
    def extract_uid(self, data):
        return str(data['sub'])
    
    def extract_common_fields(self, data):
        return {
            'username': data.get('username'),
            'email': data.get('email'),
            'first_name': data.get('given_name', ''),
            'last_name': data.get('family_name', ''),
        }


provider_classes = [MediaWikiProvider]
