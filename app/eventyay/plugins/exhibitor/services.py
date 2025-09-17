import logging
import secrets
import string
from typing import Dict, List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class ExhibitorKeyService:
    """Service for managing exhibitor authentication keys."""
    
    @staticmethod
    def generate_key(length: int = 8) -> str:
        """Generate a secure random key for exhibitor authentication."""
        alphabet = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def regenerate_key(exhibitor) -> str:
        """Regenerate a new key for an exhibitor."""
        from .models import ExhibitorInfo
        
        # Generate new key ensuring uniqueness
        max_attempts = 10
        for _ in range(max_attempts):
            new_key = ExhibitorKeyService.generate_key()
            if not ExhibitorInfo.objects.filter(key=new_key).exists():
                exhibitor.key = new_key
                exhibitor.save(update_fields=['key'])
                logger.info(f"Generated new key for exhibitor {exhibitor.id}")
                return new_key
        
        raise ValidationError("Could not generate unique key after multiple attempts")


class BoothIdService:
    """Service for managing booth ID generation and assignment."""
    
    @staticmethod
    def generate_booth_id(length: int = 8) -> str:
        """Generate a unique booth ID."""
        from .models import ExhibitorInfo
        
        characters = string.ascii_letters + string.digits
        max_attempts = 10
        
        for _ in range(max_attempts):
            booth_id = ''.join(secrets.choice(characters) for _ in range(length))
            if not ExhibitorInfo.objects.filter(booth_id=booth_id).exists():
                return booth_id
        
        raise ValidationError("Could not generate unique booth ID after multiple attempts")
    
    @staticmethod
    def assign_booth_id(exhibitor, booth_id: Optional[str] = None) -> str:
        """Assign a booth ID to an exhibitor."""
        if booth_id:
            # Validate provided booth ID is unique
            from .models import ExhibitorInfo
            if ExhibitorInfo.objects.filter(booth_id=booth_id).exclude(id=exhibitor.id).exists():
                raise ValidationError(f"Booth ID '{booth_id}' is already in use")
            exhibitor.booth_id = booth_id
        else:
            # Generate new booth ID
            exhibitor.booth_id = BoothIdService.generate_booth_id()
        
        exhibitor.save(update_fields=['booth_id'])
        logger.info(f"Assigned booth ID {exhibitor.booth_id} to exhibitor {exhibitor.id}")
        return exhibitor.booth_id


class LeadService:
    """Service for managing lead scanning and data."""
    
    @staticmethod
    def create_lead(exhibitor, attendee_data: Dict, scan_data: Dict) -> 'Lead':
        """Create a new lead from scanned attendee data."""
        from .models import Lead
        
        # Check for duplicate scan
        if Lead.objects.filter(
            exhibitor=exhibitor,
            pseudonymization_id=scan_data['pseudonymization_id']
        ).exists():
            raise ValidationError("This attendee has already been scanned by this exhibitor")
        
        # Create lead with validated data
        lead = Lead.objects.create(
            exhibitor=exhibitor,
            exhibitor_name=exhibitor.name,
            pseudonymization_id=scan_data['pseudonymization_id'],
            scanned=timezone.now(),
            scan_type=scan_data.get('scan_type', 'manual'),
            device_name=scan_data.get('device_name', 'unknown'),
            booth_id=exhibitor.booth_id,
            booth_name=exhibitor.booth_name,
            attendee=attendee_data
        )
        
        logger.info(f"Created lead {lead.id} for exhibitor {exhibitor.id}")
        return lead
    
    @staticmethod
    def update_lead_notes(lead, notes: str, tags: List[str] = None) -> 'Lead':
        """Update lead notes and tags."""
        attendee_data = lead.attendee or {}
        attendee_data['note'] = notes
        
        if tags is not None:
            attendee_data['tags'] = tags
            # Update tag usage counts
            LeadService._update_tag_usage(lead.exhibitor, tags)
        
        lead.attendee = attendee_data
        lead.save(update_fields=['attendee'])
        
        logger.info(f"Updated notes for lead {lead.id}")
        return lead
    
    @staticmethod
    def _update_tag_usage(exhibitor, tags: List[str]):
        """Update usage counts for tags."""
        from .models import ExhibitorTag
        
        for tag_name in tags:
            tag, created = ExhibitorTag.objects.get_or_create(
                exhibitor=exhibitor,
                name=tag_name,
                defaults={'use_count': 1}
            )
            if not created:
                tag.use_count += 1
                tag.save(update_fields=['use_count'])
    
    @staticmethod
    def get_lead_statistics(exhibitor) -> Dict:
        """Get lead statistics for an exhibitor."""
        from .models import Lead
        
        leads = Lead.objects.filter(exhibitor=exhibitor)
        
        return {
            'total_leads': leads.count(),
            'leads_today': leads.filter(
                scanned__date=timezone.now().date()
            ).count(),
            'leads_this_week': leads.filter(
                scanned__gte=timezone.now() - timezone.timedelta(days=7)
            ).count(),
            'follow_up_pending': leads.filter(
                follow_up_status='pending'
            ).count(),
            'follow_up_contacted': leads.filter(
                follow_up_status='contacted'
            ).count(),
            'follow_up_qualified': leads.filter(
                follow_up_status='qualified'
            ).count(),
            'follow_up_converted': leads.filter(
                follow_up_status='converted'
            ).count(),
        }


class AttendeeDataService:
    """Service for managing attendee data access and privacy."""
    
    @staticmethod
    def get_allowed_attendee_data(order_position, settings, exhibitor) -> Dict:
        """Get allowed attendee data based on privacy settings."""
        allowed_fields = settings.all_allowed_fields
        
        attendee_data = {
            'name': order_position.attendee_name,  # Always included
            'email': order_position.attendee_email,  # Always included
        }
        
        # Add optional fields based on settings
        if hasattr(order_position, 'company') and 'attendee_company' in allowed_fields:
            attendee_data['company'] = order_position.company
        
        if hasattr(order_position, 'city') and 'attendee_city' in allowed_fields:
            attendee_data['city'] = order_position.city
        
        if hasattr(order_position, 'country') and 'attendee_country' in allowed_fields:
            attendee_data['country'] = str(order_position.country)
        
        # Initialize empty fields for notes and tags
        attendee_data.update({
            'note': '',
            'tags': []
        })
        
        # Filter out None values
        return {k: v for k, v in attendee_data.items() if v is not None}
    
    @staticmethod
    def validate_field_access(field_name: str, settings) -> bool:
        """Validate if a field can be accessed based on settings."""
        return field_name in settings.all_allowed_fields


class ExhibitorIntegrationService:
    """Service for integrating exhibitors with other system components."""
    
    @staticmethod
    def get_exhibitor_tickets(exhibitor):
        """Get all tickets associated with an exhibitor."""
        return exhibitor.item_assignments.select_related('item').all()
    
    @staticmethod
    def assign_ticket_to_exhibitor(exhibitor, item):
        """Assign a ticket type to an exhibitor."""
        from .models import ExhibitorItem
        
        exhibitor_item, created = ExhibitorItem.objects.get_or_create(
            exhibitor=exhibitor,
            item=item
        )
        
        if created:
            logger.info(f"Assigned ticket {item.id} to exhibitor {exhibitor.id}")
        
        return exhibitor_item
    
    @staticmethod
    def get_exhibitor_sales_data(exhibitor) -> Dict:
        """Get sales statistics for exhibitor tickets."""
        # This would integrate with the tickets system
        # Implementation depends on the actual ticket model structure
        items = exhibitor.item_assignments.values_list('item', flat=True)
        
        # Placeholder for actual implementation
        return {
            'total_sold': 0,
            'total_revenue': 0,
            'items': list(items)
        }