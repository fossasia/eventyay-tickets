from rest_framework import permissions
from .models import ExhibitorInfo, ExhibitorStaff


class ExhibitorPermission(permissions.BasePermission):
    """Custom permission for exhibitor operations"""
    
    def has_permission(self, request, view):
        """Check if user has permission to access exhibitor endpoints"""
        # Allow read access to everyone
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Require authentication for write operations
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user has permission to access specific exhibitor"""
        # Allow read access to everyone for active exhibitors
        if request.method in permissions.SAFE_METHODS:
            if isinstance(obj, ExhibitorInfo):
                return obj.is_active or self._user_can_manage_exhibitor(request.user, obj)
            return True
        
        # For write operations, check if user can manage this exhibitor
        if isinstance(obj, ExhibitorInfo):
            return self._user_can_manage_exhibitor(request.user, obj)
        
        return False
    
    def _user_can_manage_exhibitor(self, user, exhibitor):
        """Check if user can manage the given exhibitor"""
        if not user or not user.is_authenticated:
            return False
        
        # Staff users can manage all exhibitors
        if user.is_staff or user.is_superuser:
            return True
        
        # Check if user is assigned as staff to this exhibitor
        return ExhibitorStaff.objects.filter(
            exhibitor=exhibitor,
            user=user,
            can_edit_info=True
        ).exists()


class ExhibitorStaffPermission(permissions.BasePermission):
    """Permission for exhibitor staff operations"""
    
    def has_permission(self, request, view):
        """Check if user has permission to access staff endpoints"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user has permission to manage staff"""
        if isinstance(obj, ExhibitorStaff):
            exhibitor = obj.exhibitor
        else:
            exhibitor = obj
        
        # Staff users can manage all
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Check if user is admin of this exhibitor
        return ExhibitorStaff.objects.filter(
            exhibitor=exhibitor,
            user=request.user,
            role='admin'
        ).exists()


class LeadPermission(permissions.BasePermission):
    """Permission for lead management operations"""
    
    def has_permission(self, request, view):
        """Check if user has permission to access lead endpoints"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user has permission to manage leads"""
        # Staff users can manage all leads
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Check if user can manage leads for this exhibitor
        return ExhibitorStaff.objects.filter(
            exhibitor=obj.exhibitor,
            user=request.user,
            can_manage_leads=True
        ).exists()


class ContactRequestPermission(permissions.BasePermission):
    """Permission for contact request operations"""
    
    def has_permission(self, request, view):
        """Check if user has permission to access contact request endpoints"""
        # Allow POST for creating contact requests (public)
        if request.method == 'POST':
            return True
        
        # Require authentication for other operations
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user has permission to manage contact requests"""
        # Staff users can manage all contact requests
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Check if user is staff of the exhibitor
        return ExhibitorStaff.objects.filter(
            exhibitor=obj.exhibitor,
            user=request.user
        ).exists()


class IsExhibitorStaffOrReadOnly(permissions.BasePermission):
    """Permission that allows exhibitor staff to edit, others to read only"""
    
    def has_permission(self, request, view):
        """Allow read access to all, write access to authenticated users"""
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Allow read access to all, write access to exhibitor staff"""
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Get exhibitor from object
        if hasattr(obj, 'exhibitor'):
            exhibitor = obj.exhibitor
        elif isinstance(obj, ExhibitorInfo):
            exhibitor = obj
        else:
            return False
        
        # Staff users can edit all
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Check if user is staff of this exhibitor
        return ExhibitorStaff.objects.filter(
            exhibitor=exhibitor,
            user=request.user
        ).exists()


class IsOwnerOrStaffReadOnly(permissions.BasePermission):
    """Permission that allows owners to edit, staff to read"""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Staff can read all
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_staff or request.user.is_superuser
        
        # Only owners can edit
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return request.user.is_staff or request.user.is_superuser