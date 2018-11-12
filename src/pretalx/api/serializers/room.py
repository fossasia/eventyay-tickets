from i18nfield.rest_framework import I18nAwareModelSerializer
from rest_framework.serializers import (
    ModelSerializer
)

from pretalx.schedule.models import Room, Availability


class AvailabilitySerializer(ModelSerializer):
    class Meta:
        model = Availability
        fields = ('start', 'end')


class RoomSerializer(I18nAwareModelSerializer):
    class Meta:
        model = Room
        fields = ('id', 'name', 'description', 'capacity', 'position')


class RoomOrgaSerializer(RoomSerializer):
    availabilities = AvailabilitySerializer(many=True)

    class Meta:
        model = Room
        fields = RoomSerializer.Meta.fields + ('speaker_info', 'availabilities')
