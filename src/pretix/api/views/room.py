from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from rest_framework import status, views
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from pretix.api.auth.device import DeviceTokenAuthentication
from pretix.api.auth.permission import EventPermission
from pretix.api.serializers.order import CheckinListOrderPositionSerializer
from pretix.base.models import Device, OrderPosition, Room, RoomCheckin, CheckinList, Checkin
from pretix.base.models.organizer import TeamAPIToken
from pretix.base.services.checkin import CheckInError
from pretix.helpers.database import rolledback_transaction


class RoomCheckinView(views.APIView):
    """
    API endpoint for room-specific check-in operations.
    Allows checking attendees into specific rooms independently from main event check-in.
    """
    permission_required = ('can_change_orders', 'can_checkin_orders')
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [EventPermission]

    def post(self, request, *args, **kwargs):
        """
        Check an attendee into a specific room.
        
        Expected payload:
        {
            "secret": "ticket_secret_or_barcode",
            "force": false,
            "datetime": "2023-12-01T10:00:00Z",  # optional
            "nonce": "unique_string"  # optional
        }
        """
        room_id = kwargs.get('room_id')
        
        try:
            room = Room.objects.get(
                id=room_id,
                event=request.event,
                is_active=True
            )
        except Room.DoesNotExist:
            raise Http404(_("Room not found or inactive"))
        
        # Validate device gate permissions for this room
        if isinstance(request.auth, Device):
            device_gate = request.auth.gate
            if not device_gate:
                raise PermissionDenied(_("Device must be associated with a gate for room check-in"))
            
            # Check if the room is associated with this gate
            if not room.gates.filter(id=device_gate.id).exists():
                raise PermissionDenied(_("Device gate not authorized for this room"))
        
        # Extract and validate request data
        secret = request.data.get('secret')
        if not secret:
            return Response(
                {'error': _('Secret/barcode is required')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        force = request.data.get('force', False)
        checkin_datetime = request.data.get('datetime')
        if checkin_datetime:
            try:
                from django.utils.dateparse import parse_datetime
                checkin_datetime = parse_datetime(checkin_datetime)
            except (ValueError, TypeError):
                return Response(
                    {'error': _('Invalid datetime format')},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            checkin_datetime = now()
        
        nonce = request.data.get('nonce')
        
        # Find the order position
        try:
            position = OrderPosition.objects.select_related(
                'order', 'order__event', 'item', 'variation'
            ).get(
                order__event=request.event,
                secret=secret
            )
        except OrderPosition.DoesNotExist:
            return Response(
                {
                    'status': 'error',
                    'reason': _('Ticket not found'),
                    'error_code': 'ticket_not_found'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if order is paid (unless force is used)
        if not force and position.order.status != position.order.STATUS_PAID:
            return Response(
                {
                    'status': 'error',
                    'reason': _('Order not paid'),
                    'error_code': 'order_not_paid'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check room capacity
        if not force and room.capacity and room.current_occupancy >= room.capacity:
            return Response(
                {
                    'status': 'error',
                    'reason': _('Room is at capacity'),
                    'error_code': 'room_at_capacity',
                    'current_occupancy': room.current_occupancy,
                    'capacity': room.capacity
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already checked into this room
        last_checkin = RoomCheckin.objects.filter(
            room=room,
            position=position
        ).order_by('-datetime').first()
        
        if last_checkin and last_checkin.type == RoomCheckin.TYPE_ENTRY:
            # Check if there's a more recent exit
            last_exit = RoomCheckin.objects.filter(
                room=room,
                position=position,
                type=RoomCheckin.TYPE_EXIT,
                datetime__gt=last_checkin.datetime
            ).first()
            
            if not last_exit and not force:
                return Response(
                    {
                        'status': 'error',
                        'reason': _('Already checked into this room'),
                        'error_code': 'already_checked_in',
                        'last_checkin': last_checkin.datetime.isoformat()
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Perform the check-in
        try:
            with transaction.atomic():
                # Create room check-in entry
                room_checkin = RoomCheckin.objects.create(
                    room=room,
                    position=position,
                    datetime=checkin_datetime,
                    type=RoomCheckin.TYPE_ENTRY,
                    device=request.auth if isinstance(request.auth, Device) else None,
                    gate=request.auth.gate if isinstance(request.auth, Device) and request.auth.gate else None,
                    nonce=nonce,
                    forced=force
                )
                
                # Create corresponding check-in in gate-specific check-in list
                if isinstance(request.auth, Device) and request.auth.gate:
                    gate_checkin_lists = CheckinList.objects.filter(
                        event=request.event,
                        gates=request.auth.gate
                    )
                    
                    for checkin_list in gate_checkin_lists:
                        # Only create checkin if position is valid for this list
                        if checkin_list.positions.filter(id=position.id).exists():
                            Checkin.objects.create(
                                position=position,
                                list=checkin_list,
                                datetime=checkin_datetime,
                                device=request.auth,
                                gate=request.auth.gate,
                                type=Checkin.TYPE_ENTRY,
                                nonce=nonce,
                                forced=force
                            )
                
                # Log the action
                position.order.log_action(
                    'pretix.event.room.checkin',
                    data={
                        'position': position.id,
                        'positionid': position.positionid,
                        'room': room.id,
                        'room_name': room.name,
                        'datetime': checkin_datetime,
                        'forced': force,
                        'device': request.auth.id if isinstance(request.auth, Device) else None,
                    },
                    user=request.user if request.user.is_authenticated else None,
                    auth=request.auth
                )
                
                return Response(
                    {
                        'status': 'ok',
                        'checkin_id': room_checkin.id,
                        'room': {
                            'id': room.id,
                            'name': room.name,
                            'identifier': room.identifier,
                            'current_occupancy': room.current_occupancy,
                            'capacity': room.capacity
                        },
                        'position': CheckinListOrderPositionSerializer(
                            position,
                            context={'request': request}
                        ).data,
                        'datetime': checkin_datetime.isoformat(),
                        'pseudonymization_id': room_checkin.pseudonymization_id
                    },
                    status=status.HTTP_201_CREATED
                )
                
        except Exception as e:
            return Response(
                {
                    'status': 'error',
                    'reason': _('Check-in failed'),
                    'error_code': 'checkin_failed',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RoomCheckoutView(views.APIView):
    """
    API endpoint for room-specific check-out operations.
    Allows checking attendees out of specific rooms.
    """
    permission_required = ('can_change_orders', 'can_checkin_orders')
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [EventPermission]

    def post(self, request, *args, **kwargs):
        """
        Check an attendee out of a specific room.
        
        Expected payload:
        {
            "secret": "ticket_secret_or_barcode",
            "force": false,
            "datetime": "2023-12-01T11:00:00Z",  # optional
            "nonce": "unique_string"  # optional
        }
        """
        room_id = kwargs.get('room_id')
        
        try:
            room = Room.objects.get(
                id=room_id,
                event=request.event,
                is_active=True
            )
        except Room.DoesNotExist:
            raise Http404(_("Room not found or inactive"))
        
        # Validate device gate permissions for this room
        if isinstance(request.auth, Device):
            device_gate = request.auth.gate
            if not device_gate:
                raise PermissionDenied(_("Device must be associated with a gate for room check-out"))
            
            # Check if the room is associated with this gate
            if not room.gates.filter(id=device_gate.id).exists():
                raise PermissionDenied(_("Device gate not authorized for this room"))
        
        # Extract and validate request data
        secret = request.data.get('secret')
        if not secret:
            return Response(
                {'error': _('Secret/barcode is required')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        force = request.data.get('force', False)
        checkout_datetime = request.data.get('datetime')
        if checkout_datetime:
            try:
                from django.utils.dateparse import parse_datetime
                checkout_datetime = parse_datetime(checkout_datetime)
            except (ValueError, TypeError):
                return Response(
                    {'error': _('Invalid datetime format')},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            checkout_datetime = now()
        
        nonce = request.data.get('nonce')
        
        # Find the order position
        try:
            position = OrderPosition.objects.select_related(
                'order', 'order__event', 'item', 'variation'
            ).get(
                order__event=request.event,
                secret=secret
            )
        except OrderPosition.DoesNotExist:
            return Response(
                {
                    'status': 'error',
                    'reason': _('Ticket not found'),
                    'error_code': 'ticket_not_found'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if currently checked into this room
        last_checkin = RoomCheckin.objects.filter(
            room=room,
            position=position,
            type=RoomCheckin.TYPE_ENTRY
        ).order_by('-datetime').first()
        
        if not last_checkin:
            return Response(
                {
                    'status': 'error',
                    'reason': _('Not checked into this room'),
                    'error_code': 'not_checked_in'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already checked out
        last_checkout = RoomCheckin.objects.filter(
            room=room,
            position=position,
            type=RoomCheckin.TYPE_EXIT,
            datetime__gt=last_checkin.datetime
        ).first()
        
        if last_checkout and not force:
            return Response(
                {
                    'status': 'error',
                    'reason': _('Already checked out of this room'),
                    'error_code': 'already_checked_out',
                    'last_checkout': last_checkout.datetime.isoformat()
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Perform the check-out
        try:
            with transaction.atomic():
                # Create room check-out entry
                room_checkout = RoomCheckin.objects.create(
                    room=room,
                    position=position,
                    datetime=checkout_datetime,
                    type=RoomCheckin.TYPE_EXIT,
                    device=request.auth if isinstance(request.auth, Device) else None,
                    gate=request.auth.gate if isinstance(request.auth, Device) and request.auth.gate else None,
                    nonce=nonce,
                    forced=force
                )
                
                # Create corresponding check-out in gate-specific check-in list
                if isinstance(request.auth, Device) and request.auth.gate:
                    gate_checkin_lists = CheckinList.objects.filter(
                        event=request.event,
                        gates=request.auth.gate
                    )
                    
                    for checkin_list in gate_checkin_lists:
                        # Only create checkout if position is valid for this list
                        if checkin_list.positions.filter(id=position.id).exists():
                            Checkin.objects.create(
                                position=position,
                                list=checkin_list,
                                datetime=checkout_datetime,
                                device=request.auth,
                                gate=request.auth.gate,
                                type=Checkin.TYPE_EXIT,
                                nonce=nonce,
                                forced=force
                            )
                
                # Calculate duration
                duration = room_checkout.duration_in_room
                
                # Log the action
                position.order.log_action(
                    'pretix.event.room.checkout',
                    data={
                        'position': position.id,
                        'positionid': position.positionid,
                        'room': room.id,
                        'room_name': room.name,
                        'datetime': checkout_datetime,
                        'duration_seconds': duration.total_seconds() if duration else None,
                        'forced': force,
                        'device': request.auth.id if isinstance(request.auth, Device) else None,
                    },
                    user=request.user if request.user.is_authenticated else None,
                    auth=request.auth
                )
                
                return Response(
                    {
                        'status': 'ok',
                        'checkout_id': room_checkout.id,
                        'room': {
                            'id': room.id,
                            'name': room.name,
                            'identifier': room.identifier,
                            'current_occupancy': room.current_occupancy,
                            'capacity': room.capacity
                        },
                        'position': CheckinListOrderPositionSerializer(
                            position,
                            context={'request': request}
                        ).data,
                        'datetime': checkout_datetime.isoformat(),
                        'duration_seconds': duration.total_seconds() if duration else None,
                        'pseudonymization_id': room_checkout.pseudonymization_id
                    },
                    status=status.HTTP_201_CREATED
                )
                
        except Exception as e:
            return Response(
                {
                    'status': 'error',
                    'reason': _('Check-out failed'),
                    'error_code': 'checkout_failed',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RoomStatusView(views.APIView):
    """
    API endpoint to get real-time room status and occupancy information.
    """
    permission_required = ('can_view_orders', 'can_checkin_orders')
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [EventPermission]

    def get(self, request, *args, **kwargs):
        """
        Get current status and occupancy for a specific room.
        """
        room_id = kwargs.get('room_id')
        
        try:
            room = Room.objects.get(
                id=room_id,
                event=request.event
            )
        except Room.DoesNotExist:
            raise Http404(_("Room not found"))
        
        # Get recent check-ins (last 24 hours)
        from datetime import timedelta
        recent_checkins = RoomCheckin.objects.filter(
            room=room,
            datetime__gte=now() - timedelta(hours=24)
        ).select_related('position', 'position__order').order_by('-datetime')[:50]
        
        # Calculate occupancy statistics
        total_checkins_today = RoomCheckin.objects.filter(
            room=room,
            type=RoomCheckin.TYPE_ENTRY,
            datetime__date=now().date()
        ).count()
        
        total_checkouts_today = RoomCheckin.objects.filter(
            room=room,
            type=RoomCheckin.TYPE_EXIT,
            datetime__date=now().date()
        ).count()
        
        return Response(
            {
                'room': {
                    'id': room.id,
                    'name': room.name,
                    'identifier': room.identifier,
                    'description': room.description,
                    'location': room.location,
                    'capacity': room.capacity,
                    'session_start': room.session_start.isoformat() if room.session_start else None,
                    'session_end': room.session_end.isoformat() if room.session_end else None,
                    'is_active': room.is_active
                },
                'occupancy': {
                    'current': room.current_occupancy,
                    'capacity': room.capacity,
                    'is_at_capacity': room.is_at_capacity,
                    'utilization_percentage': (
                        round((room.current_occupancy / room.capacity) * 100, 1)
                        if room.capacity else None
                    )
                },
                'statistics': {
                    'total_checkins_today': total_checkins_today,
                    'total_checkouts_today': total_checkouts_today,
                    'net_entries_today': total_checkins_today - total_checkouts_today
                },
                'recent_activity': [
                    {
                        'id': checkin.id,
                        'type': checkin.type,
                        'datetime': checkin.datetime.isoformat(),
                        'position_id': checkin.position.id,
                        'attendee_name': checkin.position.attendee_name,
                        'order_code': checkin.position.order.code,
                        'pseudonymization_id': checkin.pseudonymization_id
                    }
                    for checkin in recent_checkins
                ]
            },
            status=status.HTTP_200_OK
        )