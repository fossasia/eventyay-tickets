from rest_framework.serializers import ModelSerializer

from pretalx.person.models import User


class SubmitterSerializer(ModelSerializer):

    class Meta:
        model = User
        fields = (
            'code', 'name',
        )
