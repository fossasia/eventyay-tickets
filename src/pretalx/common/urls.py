from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.urls import reverse
from urlman import Urls


def get_base_url(event=None):
    if event and event.settings.custom_url:
        return event.settings.custom_url
    return settings.SITE_URL


def build_absolute_uri(urlname, event=None, args=None, kwargs=None):
    url = get_base_url(event)
    return urljoin(url, reverse(urlname, args=args, kwargs=kwargs))


class EventUrls(Urls):

    def get_hostname(self, url):
        url = get_base_url(self.instance.event)
        return urlparse(url).netloc

    def get_scheme(self, url):
        url = get_base_url(self.instance.event)
        return urlparse(url).scheme
