from rest_framework.fields import UUIDField
from rest_framework.serializers import ModelSerializer

from ..models.auth import User


class PublicUserSerializer(ModelSerializer):
    id = UUIDField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "profile")
