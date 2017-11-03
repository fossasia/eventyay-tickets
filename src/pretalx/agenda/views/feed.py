from urllib.parse import urlencode

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.utils import feedgenerator


class ScheduleFeed(Feed):

    feed_type = feedgenerator.Atom1Feed
    description_template = 'agenda/feed/description.html'

    def get_object(self, request, event, *args, **kwargs):
        return request.event

    def title(self, obj):
        return f'{obj.name} schedule updates'

    def link(self, obj):
        return obj.urls.schedule.full(scheme='https', hostname=settings.SITE_NETLOC)

    def feed_url(self, obj):
        return obj.urls.feed.full(scheme='https', hostname=settings.SITE_NETLOC)

    def feed_guid(self, obj):
        return obj.urls.feed.full(scheme='https', hostname=settings.SITE_NETLOC)

    def description(self, obj):
        return f'Updates to the {obj.name} schedule.'

    def items(self, obj):
        return obj.schedules.filter(version__isnull=False).order_by('-published')

    def item_title(self, item):
        return f'New {item.event.name} schedule released ({item.version})'

    def item_link(self, item):
        url = item.event.urls.schedule.full(scheme='https', hostname=settings.SITE_NETLOC)
        version = {'version': item.version}
        return f'{url}={urlencode(version)}'

    def item_pubdate(self, item):
        return item.published
