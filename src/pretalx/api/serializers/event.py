from django_scopes import scopes_disabled
from rest_framework.serializers import ModelSerializer

from pretalx.event.models import Event

with scopes_disabled():
    class EventSerializer(ModelSerializer):
        class Meta:
            model = Event
            fields = (
                'name',
                'slug',
                'is_public',
                'date_from',
                'date_to',
                'timezone',
                'html_export_url',
            )
