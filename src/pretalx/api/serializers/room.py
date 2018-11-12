from i18nfield.rest_framework import I18nAwareModelSerializer
from rest_framework.serializers import (
    ModelSerializer, SerializerMethodField, SlugRelatedField,
)

from pretalx.schedule.models import Room


class RoomSerializer(I18nAwareModelSerializer):
    class Meta:
        model = Room
        fields = ('id', 'name', 'description', 'capacity', 'position')


class RoomOrgaSerializer(RoomSerializer):
    class Meta:
        model = Room
        fields = RoomSerializer.Meta.fields + ('speaker_info',)
