from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.urls import reverse
from urlman import Urls


def build_absolute_uri(urlname, args=None, kwargs=None):
    return urljoin(settings.SITE_URL, reverse(urlname, args=args, kwargs=kwargs))


class EventUrls(Urls):

    def get_netloc(self, url):
        if self.instance.event and self.instance.event.settings.custom_url:
            url = self.instance.event.settings.custom_url
        else:
            url = settings.SITE_URL
        return urlparse(url).netloc

    def get_scheme(self, url):
        if self.instance.event and self.instance.event.settings.custom_url:
            url = self.instance.event.settings.custom_url
        else:
            url = settings.SITE_URL
        return urlparse(url).scheme
