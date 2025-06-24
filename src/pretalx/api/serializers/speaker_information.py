from pathlib import Path

from rest_flex_fields.serializers import FlexFieldsSerializerMixin

from pretalx.api.mixins import PretalxSerializer
from pretalx.api.serializers.fields import UploadedFileField
from pretalx.api.versions import CURRENT_VERSIONS, register_serializer
from pretalx.person.models import SpeakerInformation
from pretalx.submission.models import SubmissionType, Track


@register_serializer(versions=CURRENT_VERSIONS)
class SpeakerInformationSerializer(FlexFieldsSerializerMixin, PretalxSerializer):
    resource = UploadedFileField(required=False)

    class Meta:
        model = SpeakerInformation
        fields = (
            "id",
            "target_group",
            "title",
            "text",
            "resource",
            "limit_tracks",
            "limit_types",
        )
        expandable_fields = {
            "limit_tracks": (
                "pretalx.api.serializers.submission.TrackSerializer",
                {"many": True, "read_only": True},
            ),
            "limit_types": (
                "pretalx.api.serializers.submission.SubmissionTypeSerializer",
                {"many": True, "read_only": True},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.event:
            self.fields["limit_tracks"].queryset = self.event.tracks.all()
            self.fields["limit_types"].queryset = self.event.submission_types.all()
        else:
            self.fields["limit_tracks"].queryset = Track.objects.none()
            self.fields["limit_types"].queryset = SubmissionType.objects.none()

    def create(self, validated_data):
        validated_data["event"] = self.event
        resource = validated_data.pop("resource", None)
        instance = super().create(validated_data)
        if resource:
            instance.resource.save(Path(resource.name).name, resource, save=False)
            instance.save(update_fields=("resource",))
        return instance

    def update(self, instance, validated_data):
        resource = validated_data.pop("resource", None)
        instance = super().update(instance, validated_data)
        if resource:
            instance.resource.update(Path(resource.name).name, resource)
        return instance
