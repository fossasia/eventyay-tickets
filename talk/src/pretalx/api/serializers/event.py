from rest_framework.serializers import ModelSerializer

from pretalx.api.serializers.fields import UploadedFileField
from pretalx.api.versions import register_serializer
from pretalx.event.models import Event


@register_serializer()
class EventListSerializer(ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "name",
            "slug",
            "is_public",
            "date_from",
            "date_to",
            "timezone",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        try:
            if not request or not request.user or not request.user.is_authenticated:
                # Keep API docs small; doesn’t matter for validation with unauthenticated
                # users.
                self.fields["timezone"].choices = []
        except Exception as e:
            print(e)


@register_serializer()
class EventSerializer(EventListSerializer):
    logo = UploadedFileField(required=False)

    class Meta(EventListSerializer.Meta):
        fields = EventListSerializer.Meta.fields + [
            "email",  # Email is public in the footer anyway
            "primary_color",
            "custom_domain",
            "logo",
            "header_image",
            "locale",
            "locales",
            "content_locales",
        ]
