from rest_framework.fields import Field, IntegerField, UUIDField
from rest_framework.serializers import ModelSerializer

from ..models import ChatEvent


class StaticTypeField(Field):
    def to_representation(self, v):
        return "chat.event"


class ChatEventSerializer(ModelSerializer):
    event_id = IntegerField(source="id")
    channel = UUIDField(source="channel_id")
    sender = UUIDField(source="sender_id")
    type = StaticTypeField(source="id")

    class Meta:
        model = ChatEvent
        fields = (
            "event_id",
            "channel",
            "timestamp",
            "event_type",
            "sender",
            "content",
            "timestamp",
            "type",
        )
