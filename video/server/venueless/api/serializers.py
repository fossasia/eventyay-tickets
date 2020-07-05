from rest_framework import serializers

from venueless.core.models import World

from ..core.models import Room


class RoomSerializer(serializers.ModelSerializer):
    module_config = serializers.ListField(
        child=serializers.DictField(), required=False, default=[]
    )
    trait_grants = serializers.DictField(required=False, default={})

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
            # TODO: picture
        ]


class WorldSerializer(serializers.ModelSerializer):
    config = serializers.DictField()
    trait_grants = serializers.DictField()
    roles = serializers.DictField()

    class Meta:
        model = World
        fields = [
            "id",
            "title",
            "config",
            "trait_grants",
            "roles",
            "domain",
        ]
