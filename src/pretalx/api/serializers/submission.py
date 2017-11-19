from rest_framework.serializers import ModelSerializer

from pretalx.api.serializers.speaker import SubmitterSerializer
from pretalx.schedule.models import Schedule
from pretalx.submission.models import Submission


class SubmissionSerializer(ModelSerializer):
    speakers = SubmitterSerializer(many=True)

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
