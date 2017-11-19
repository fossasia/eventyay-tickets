from rest_framework import viewsets

from pretalx.api.serializers.speaker import SubmitterSerializer
from pretalx.person.models import SpeakerProfile


class SubmitterViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubmitterSerializer
    queryset = SpeakerProfile.objects.none()
    lookup_field = 'slug'
    lookup_url_kwarg = 'event'
    """ TODO: infer filter from URL """
