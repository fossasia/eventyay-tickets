from rest_framework import viewsets, views, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from pretix.api.serializers.i18n import I18nAwareModelSerializer
from pretix.api.serializers.order import CompatibleJSONField

from .models import ExhibitorInfo, ExhibitorItem


class ExhibitorAuthView(views.APIView):
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        key = request.data.get('key')

        if not email or not key:
            return Response(
                {'detail': 'Missing parameters'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            exhibitor = ExhibitorInfo.objects.get(email=email, key=key)
            return Response(
                {'success': True, 'exhibitor_id': exhibitor.id},
                status=status.HTTP_200_OK
            )
        except ExhibitorInfo.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class ExhibitorItemAssignmentSerializer(I18nAwareModelSerializer):
    class Meta:
        model = ExhibitorItem
        fields = ('id', 'item', 'exhibitor')


class NestedItemAssignmentSerializer(I18nAwareModelSerializer):
    class Meta:
        model = ExhibitorItem
        fields = ('item',)


class ExhibitorInfoSerializer(I18nAwareModelSerializer):
    class Meta:
        model = ExhibitorInfo
        fields = ('id', 'name', 'description', 'url', 'email', 'logo', 'key', 'lead_scanning_enabled')


class ExhibitorInfoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ExhibitorInfoSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return ExhibitorInfo.objects.filter(event=self.request.event)


class ExhibitorItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ExhibitorItemAssignmentSerializer
    queryset = ExhibitorItem.objects.none()
    lookup_field = 'id'

    def get_queryset(self):
        return ExhibitorItem.objects.filter(item__event=self.request.event)
