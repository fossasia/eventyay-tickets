from rest_framework import serializers

from eventyay.api.serializers.fields import UploadedFileField
from eventyay.api.serializers.i18n import I18nAwareModelSerializer
from eventyay.base.models.event import Event
from django.conf import settings
from eventyay.consts import SizeKey
from eventyay.base.models.room import Room, RoomLinkedSessionsSerializerMixin


class RoomSerializer(RoomLinkedSessionsSerializerMixin, I18nAwareModelSerializer):
    module_config = serializers.ListField(
        child=serializers.DictField(), required=False, default=[]
    )
    trait_grants = serializers.DictField(required=False, default={})

    picture = UploadedFileField(
        required=False,
        allow_null=True,
        allowed_types=('image/png', 'image/jpeg', 'image/gif', 'image/webp'),
        max_size=settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_IMAGE],
    )

    class Meta:
        model = Room
        fields = [
            "id",
            "deleted",
            "trait_grants",
            "module_config",
            "name",
            "description",
            "sorting_priority",
            "pretalx_id",
            "schedule_data",
            "is_unscheduled",
            "has_linked_sessions",
            "picture",
        ]


class EventSerializer(serializers.ModelSerializer):
    config = serializers.DictField()
    trait_grants = serializers.DictField()
    roles = serializers.DictField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "config",
            "trait_grants",
            "roles",
            "domain",
        ]
