from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.urls import reverse
from urlman import Urls


def get_base_url(event=None, url=None):
    if url and url.startswith('/orga'):
        return settings.SITE_URL
    if event and event.settings.custom_domain:
        return event.settings.custom_domain
    return settings.SITE_URL


def build_absolute_uri(urlname, event=None, args=None, kwargs=None):
    url = get_base_url(event)
    return urljoin(url, reverse(urlname, args=args, kwargs=kwargs))


class EventUrls(Urls):

    def get_hostname(self, url):
        url = get_base_url(self.instance.event)
        return urlparse(url).netloc

    def get_scheme(self, url):
        url = get_base_url(self.instance.event, url)
        return urlparse(url).scheme
