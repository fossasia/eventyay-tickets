from urllib.parse import urlencode

from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils import feedgenerator

from pretalx.event.models import Event


class ScheduleFeed(Feed):

    feed_type = feedgenerator.Atom1Feed

    description_template = 'agenda/feed/description.html'

    def get_object(self, request, event, *args, **kwargs):
        return Event.objects.get(slug=event)

    def title(self, obj):
        return f'{obj.name} schedule updates'

    def link(self, obj):
        return reverse('agenda:schedule', kwargs={'event': obj.slug})

    def feed_url(self, obj):
        return reverse('agenda:feed', kwargs={'event': obj.slug})

    def feed_guid(self, obj):
        return reverse('agenda:feed', kwargs={'event': obj.slug})

    def description(self, obj):
        return f'Updates to the {obj.name} schedule.'

    def items(self, obj):
        return obj.schedules.filter(version__isnull=False)

    def item_title(self, item):
        return f'New {item.event.name} schedule released ({item.version})'

    def item_link(self, item):
        url = reverse('agenda:schedule', kwargs={'event': item.event.slug})
        version = {'version': item.version}
        return f'{url}={urlencode(version)}'

    def item_pubdate(self, item):
        return item.published
