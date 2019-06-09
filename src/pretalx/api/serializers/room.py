from django_scopes import scopes_disabled
from i18nfield.rest_framework import I18nAwareModelSerializer
from rest_framework.serializers import ModelSerializer, SerializerMethodField

from pretalx.schedule.models import Availability, Room

with scopes_disabled():

    class AvailabilitySerializer(ModelSerializer):
        allDay = SerializerMethodField()

        def get_allDay(self, obj):
            return obj.all_day

        class Meta:
            model = Availability
            fields = ('id', 'start', 'end', 'allDay')

    class RoomSerializer(I18nAwareModelSerializer):
        url = SerializerMethodField()

        def get_url(self, obj):
            return obj.urls.edit

        class Meta:
            model = Room
            fields = ('id', 'name', 'description', 'capacity', 'position', 'url')

    class RoomOrgaSerializer(RoomSerializer):
        availabilities = AvailabilitySerializer(many=True)

        class Meta:
            model = Room
            fields = RoomSerializer.Meta.fields + ('speaker_info', 'availabilities')
