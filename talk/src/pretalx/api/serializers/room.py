from rest_framework.serializers import UUIDField

from pretalx.api.mixins import PretalxSerializer
from pretalx.api.serializers.availability import (
    AvailabilitiesMixin,
    AvailabilitySerializer,
)
from pretalx.api.versions import CURRENT_VERSIONS, register_serializer
from pretalx.schedule.models import Room


@register_serializer(versions=CURRENT_VERSIONS)
class RoomSerializer(AvailabilitiesMixin, PretalxSerializer):
    uuid = UUIDField(
        help_text="The uuid field is equal the the guid field if a guid has been set. Otherwise, it will contain a computed (stable) UUID.",
        read_only=True,
    )

    class Meta:
        model = Room
        fields = (
            "id",
            "name",
            "description",
            "uuid",
            "guid",
            "capacity",
            "position",
        )


@register_serializer(versions=CURRENT_VERSIONS)
class RoomOrgaSerializer(RoomSerializer):
    availabilities = AvailabilitySerializer(many=True, required=False)

    def create(self, validated_data):
        availabilities_data = validated_data.pop("availabilities", None)
        validated_data["event"] = getattr(self.context.get("request"), "event", None)
        room = super().create(validated_data)
        if availabilities_data is not None:
            self._handle_availabilities(room, availabilities_data, field="room")
        return room

    def update(self, instance, validated_data):
        availabilities_data = validated_data.pop("availabilities", None)
        room = super().update(instance, validated_data)
        if availabilities_data is not None:
            self._handle_availabilities(room, availabilities_data, field="room")
        return room

    class Meta:
        model = Room
        fields = RoomSerializer.Meta.fields + ("speaker_info", "availabilities")
