from urllib.parse import urlencode, urlparse, urlunparse

from allauth.socialaccount.adapter import get_adapter

from pretix.base.auth import BaseAuthBackend
from pretix.helpers.urls import build_absolute_uri

adapter = get_adapter()


class MediaWikiBackend(BaseAuthBackend):
    identifier = 'mediawiki'

    @property
    def verbose_name(self):
        return "Login with MediaWiki"

    def authentication_url(self, request):
        base_url = adapter.get_provider(request, 'mediawiki').get_login_url(request)
        query_params = {
            "next": build_absolute_uri("plugins:socialauth:social.oauth.return")
        }

        parsed_url = urlparse(base_url)
        updated_url = parsed_url._replace(query=urlencode(query_params))
        return urlunparse(updated_url)


class GoogleBackend(BaseAuthBackend):
    identifier = 'google'

    @property
    def verbose_name(self):
        return "Login with Google"

    def authentication_url(self, request):
        base_url = adapter.get_provider(request, 'google').get_login_url(request)
        query_params = {
            "next": build_absolute_uri("plugins:socialauth:social.oauth.return")
        }

        parsed_url = urlparse(base_url)
        updated_url = parsed_url._replace(query=urlencode(query_params))
        return urlunparse(updated_url)


class GithubBackend(BaseAuthBackend):
    identifier = 'github'

    @property
    def verbose_name(self):
        return "Login with Github"

    def authentication_url(self, request):
        base_url = adapter.get_provider(request, 'github').get_login_url(request)
        query_params = {
            "next": build_absolute_uri("plugins:socialauth:social.oauth.return")
        }

        parsed_url = urlparse(base_url)
        updated_url = parsed_url._replace(query=urlencode(query_params))
        return urlunparse(updated_url)
