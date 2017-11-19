from i18nfield.rest_framework import I18nAwareModelSerializer
from rest_framework.serializers import ModelSerializer, SlugRelatedField

from pretalx.api.serializers.speaker import SubmitterSerializer
from pretalx.schedule.models import Schedule
from pretalx.submission.models import Submission


class SubmissionSerializer(I18nAwareModelSerializer):
    speakers = SubmitterSerializer(many=True)
    submission_type = SlugRelatedField(slug_field='name', read_only=True)

    class Meta:
        model = Submission
        fields = (
            'code', 'speakers', 'title', 'submission_type', 'state', 'abstract',
            'description', 'duration', 'do_not_record', 'content_locale',
        )


class ScheduleSerializer(ModelSerializer):
    slots = SubmissionSerializer(many=True)

    class Meta:
        model = Schedule
        fields = (
            'slots', 'version',
        )
