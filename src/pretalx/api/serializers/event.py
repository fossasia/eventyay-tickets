from rest_framework.serializers import ModelSerializer
from urlman import UrlManField

from pretalx.event.models import Event


class EventSerializer(ModelSerializer):
    urls = UrlManField(urls=['base', 'schedule', 'login', 'feed'])

    class Meta:
        model = Event
        fields = (
            'name',
            'slug',
            'is_public',
            'date_from',
            'date_to',
            'timezone',
            'urls',
        )
