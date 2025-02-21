from django.shortcuts import get_object_or_404
from django.utils import timezone
from pretix.api.serializers.i18n import I18nAwareModelSerializer
from pretix.api.serializers.order import CompatibleJSONField
from pretix.base.models import OrderPosition
from rest_framework import status, views, viewsets
from rest_framework.response import Response
from django.core.exceptions import ObjectDoesNotExist
from .models import ExhibitorInfo, ExhibitorItem,ExhibitorSettings , ExhibitorTag, Lead


class ExhibitorAuthView(views.APIView):
    def post(self, request, *args, **kwargs):
        key = request.data.get('key')

        if not key:
            return Response(
                {'detail': 'Missing parameters'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            exhibitor = ExhibitorInfo.objects.get(key=key)
            return Response(
                {
                    'success': True,
                    'exhibitor_id': exhibitor.id,
                    'exhibitor_name': exhibitor.name,
                    'booth_id': exhibitor.booth_id,
                    'booth_name': exhibitor.booth_name,
                },
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


class LeadCreateView(views.APIView):
    def get_allowed_attendee_data(self, order_position, settings, exhibitor):
        """Helper method to get allowed attendee data based on settings"""
        # Get all allowed fields including defaults
        allowed_fields = settings.all_allowed_fields
        attendee_data = {
            'name': order_position.attendee_name,  # Always included
            'email': order_position.attendee_email,  # Always included
            'company': order_position.company if 'attendee_company' in allowed_fields else None,
            'city': order_position.city if 'attendee_city' in allowed_fields else None,
            'country': str(order_position.country) if 'attendee_country' in allowed_fields else None,
            'note': '',
            'tags': []
        }

        return {k: v for k, v in attendee_data.items() if v is not None}

    def post(self, request, *args, **kwargs):
        # Extract parameters from the request
        pseudonymization_id = request.data.get('lead')
        scanned = request.data.get('scanned')
        scan_type = request.data.get('scan_type')
        device_name = request.data.get('device_name')
        open_event = request.data.get('open_event')
        key = request.headers.get('Exhibitor')

        if not all([pseudonymization_id, scanned, scan_type, device_name]):
            return Response(
                {'detail': 'Missing parameters'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Authenticate the exhibitor
        try:
            exhibitor = ExhibitorInfo.objects.get(key=key)
            settings = ExhibitorSettings.objects.get(event=exhibitor.event)
        except (ExhibitorInfo.DoesNotExist, ExhibitorSettings.DoesNotExist):
            return Response(
                {'success': False, 'error': 'Invalid exhibitor key'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get attendee details
        try:
            if open_event:
                order_position = OrderPosition.objects.get(
                    secret = pseudonymization_id
                )
            else:
                order_position = OrderPosition.objects.get(
                    pseudonymization_id=pseudonymization_id
                )
        except OrderPosition.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Attendee not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check for duplicate scan
        if Lead.objects.filter(
            exhibitor=exhibitor,
            pseudonymization_id=pseudonymization_id
        ).exists():
            attendee_data = self.get_allowed_attendee_data(
                order_position,
                settings,
                exhibitor
            )
            return Response(
                {
                    'success': False,
                    'error': 'Lead already scanned',
                    'attendee': attendee_data
                },
                status=status.HTTP_409_CONFLICT
            )

        # Get allowed attendee data based on settings
        attendee_data = self.get_allowed_attendee_data(
            order_position,
            settings,
            exhibitor
        )
        # Create the lead entry
        lead = Lead.objects.create(
            exhibitor=exhibitor,
            exhibitor_name=exhibitor.name,
            pseudonymization_id=pseudonymization_id,
            scanned=timezone.now(),
            scan_type=scan_type,
            device_name=device_name,
            booth_id=exhibitor.booth_id,
            booth_name=exhibitor.booth_name,
            attendee=attendee_data
        )

        return Response(
            {
                'success': True,
                'lead_id': lead.id,
                'attendee': attendee_data
            },
            status=status.HTTP_201_CREATED
        )


class LeadRetrieveView(views.APIView):
    def get(self, request, *args, **kwargs):
        # Authenticate the exhibitor using the key
        key = request.headers.get('Exhibitor')
        try:
            exhibitor = ExhibitorInfo.objects.get(key=key)
        except ExhibitorInfo.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'error': 'Invalid exhibitor key'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Fetch all leads associated with the exhibitor
        leads = Lead.objects.filter(exhibitor=exhibitor).values(
            'id',
            'pseudonymization_id',
            'exhibitor_name',
            'scanned',
            'scan_type',
            'device_name',
            'booth_id',
            'booth_name',
            'attendee'
        )

        return Response(
            {
                'success': True,
                'leads': list(leads)
            },
            status=status.HTTP_200_OK
        )


class TagListView(views.APIView):
    def get(self, request, organizer, event, *args, **kwargs):
        key = request.headers.get('Exhibitor')
        try:
            exhibitor = ExhibitorInfo.objects.get(key=key)
            tags = ExhibitorTag.objects.filter(exhibitor=exhibitor)
            return Response({
                'success': True,
                'tags': [tag.name for tag in tags]
            })
        except ExhibitorInfo.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'error': 'Invalid exhibitor key'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

class LeadUpdateView(views.APIView):
    def post(self, request, organizer, event, lead_id, *args, **kwargs):
        key = request.headers.get('Exhibitor')
        note = request.data.get('note')
        tags = request.data.get('tags', [])

        try:
            exhibitor = ExhibitorInfo.objects.get(key=key)
        except ExhibitorInfo.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'error': 'Invalid exhibitor key'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            lead = Lead.objects.get(pseudonymization_id=lead_id, exhibitor=exhibitor)
        except Lead.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'error': 'Lead not found'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Update lead's attendee info
        attendee_data = lead.attendee or {}
        if note is not None:
            attendee_data['note'] = note
        if tags is not None:
            attendee_data['tags'] = tags

            # Update tag usage counts and create new tags
            for tag_name in tags:
                tag, created = ExhibitorTag.objects.get_or_create(
                    exhibitor=exhibitor,
                    name=tag_name
                )
                if not created:
                    tag.use_count += 1
                    tag.save()

        lead.attendee = attendee_data
        lead.save()
        
        return Response(
            {
                'success': True,
                'lead_id': lead.id,
                'attendee': lead.attendee
            },
            status=status.HTTP_200_OK
        )
