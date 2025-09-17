from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from .models import ExhibitorInfo


class ExhibitorKeyPermission(permissions.BasePermission):
    """
    Permission class for exhibitor key-based authentication.
    Used for mobile app access to exhibitor APIs.
    """
    
    def has_permission(self, request, view):
        """Check if the request has a valid exhibitor key."""
        exhibitor_key = request.headers.get('Exhibitor-Key')
        
        if not exhibitor_key:
            return False
        
        try:
            exhibitor = ExhibitorInfo.objects.get(key=exhibitor_key)
            # Store the exhibitor in the request for later use
            request.exhibitor = exhibitor
            return True
        except ExhibitorInfo.DoesNotExist:
            return False


class ExhibitorManagementPermission(permissions.BasePermission):
    """
    Permission class for exhibitor management operations.
    Requires event management permissions.
    """
    
    def has_permission(self, request, view):
        """Check if user has exhibitor management permissions."""
        if not request.user.is_authenticated:
            return False
        
        if not hasattr(request, 'event') or not hasattr(request, 'organizer'):
            return False
        
        return request.user.has_event_permission(
            request.organizer,
            request.event,
            'can_change_event_settings',
            request=request
        )


class LeadAccessPermission(permissions.BasePermission):
    """
    Permission class for lead data access.
    Checks both exhibitor key and privacy settings.
    """
    
    def has_permission(self, request, view):
        """Check if request has permission to access lead data."""
        # First check exhibitor key authentication
        if not ExhibitorKeyPermission().has_permission(request, view):
            return False
        
        # Check if lead scanning is enabled for this exhibitor
        if not request.exhibitor.lead_scanning_enabled:
            raise PermissionDenied("Lead scanning is not enabled for this exhibitor.")
        
        return True


class ExhibitorObjectPermission(permissions.BasePermission):
    """
    Object-level permission for exhibitor instances.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check if user has permission to access this exhibitor object."""
        # For exhibitor key authentication, only allow access to own data
        if hasattr(request, 'exhibitor'):
            return obj == request.exhibitor
        
        # For admin users, check event permissions
        if request.user.is_authenticated:
            return request.user.has_event_permission(
                obj.event.organizer,
                obj.event,
                'can_change_event_settings',
                request=request
            )
        
        return False