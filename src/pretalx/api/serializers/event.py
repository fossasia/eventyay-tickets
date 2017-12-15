from rest_framework.serializers import ModelSerializer

from pretalx.event.models import Event


class EventSerializer(ModelSerializer):

    class Meta:
        model = Event
        fields = (
            'name', 'slug', 'subtitle', 'is_public', 'date_from', 'date_to',
            'timezone', 'html_export_url'
        )
