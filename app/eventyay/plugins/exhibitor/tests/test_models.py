from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch

from eventyay.base.models import Event, Organizer
from ..models import (
    ExhibitorInfo, ExhibitorSettings, ExhibitorItem, 
    Lead, ExhibitorTag, generate_key, generate_booth_id
)


class ExhibitorInfoModelTest(TestCase):
    """Test cases for ExhibitorInfo model."""
    
    def setUp(self):
        """Set up test data."""
        self.organizer = Organizer.objects.create(
            name='Test Organizer',
            slug='test-org'
        )
        self.event = Event.objects.create(
            name='Test Event',
            slug='test-event',
            organizer=self.organizer,
            date_from=timezone.now(),
            date_to=timezone.now() + timezone.timedelta(days=1)
        )
    
    def test_exhibitor_creation(self):
        """Test basic exhibitor creation."""
        exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='Test Exhibitor',
            booth_name='Booth A1'
        )
        
        self.assertEqual(exhibitor.name, 'Test Exhibitor')
        self.assertEqual(exhibitor.booth_name, 'Booth A1')
        self.assertIsNotNone(exhibitor.key)
        self.assertEqual(len(exhibitor.key), 8)
        self.assertIsNotNone(exhibitor.booth_id)
        self.assertTrue(exhibitor.is_active)
        self.assertEqual(exhibitor.sort_order, 0)
        self.assertFalse(exhibitor.featured)
    
    def test_key_generation(self):
        """Test that access keys are generated correctly."""
        key = generate_key()
        self.assertEqual(len(key), 8)
        self.assertTrue(key.isalnum())
        self.assertTrue(key.islower())
    
    def test_booth_id_generation(self):
        """Test booth ID generation."""
        booth_id = generate_booth_id()
        self.assertEqual(len(booth_id), 8)
        self.assertTrue(booth_id.isalnum())
    
    def test_booth_id_uniqueness(self):
        """Test that booth IDs are unique."""
        exhibitor1 = ExhibitorInfo.objects.create(
            event=self.event,
            name='Exhibitor 1',
            booth_name='Booth A1'
        )
        exhibitor2 = ExhibitorInfo.objects.create(
            event=self.event,
            name='Exhibitor 2',
            booth_name='Booth A2'
        )
        
        self.assertNotEqual(exhibitor1.booth_id, exhibitor2.booth_id)
    
    def test_name_validation(self):
        """Test name validation."""
        exhibitor = ExhibitorInfo(
            event=self.event,
            name='A',  # Too short
            booth_name='Booth A1'
        )
        
        with self.assertRaises(ValidationError):
            exhibitor.clean()
    
    def test_booth_id_uniqueness_validation(self):
        """Test booth ID uniqueness validation."""
        ExhibitorInfo.objects.create(
            event=self.event,
            name='Exhibitor 1',
            booth_name='Booth A1',
            booth_id='BOOTH001'
        )
        
        exhibitor2 = ExhibitorInfo(
            event=self.event,
            name='Exhibitor 2',
            booth_name='Booth A2',
            booth_id='BOOTH001'  # Duplicate
        )
        
        with self.assertRaises(ValidationError):
            exhibitor2.clean()
    
    def test_name_stripping(self):
        """Test that names are stripped of whitespace."""
        exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='  Test Exhibitor  ',
            booth_name='Booth A1'
        )
        
        self.assertEqual(exhibitor.name, 'Test Exhibitor')
    
    def test_lead_count_property(self):
        """Test lead count property."""
        exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='Test Exhibitor',
            booth_name='Booth A1'
        )
        
        self.assertEqual(exhibitor.lead_count, 0)
        
        # Create a lead
        Lead.objects.create(
            exhibitor=exhibitor,
            exhibitor_name=exhibitor.name,
            pseudonymization_id='test123',
            scanned=timezone.now(),
            scan_type='manual',
            device_name='test-device',
            booth_id=exhibitor.booth_id,
            booth_name=exhibitor.booth_name
        )
        
        self.assertEqual(exhibitor.lead_count, 1)
    
    def test_recent_leads_count_property(self):
        """Test recent leads count property."""
        exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='Test Exhibitor',
            booth_name='Booth A1'
        )
        
        # Create an old lead
        old_date = timezone.now() - timezone.timedelta(days=10)
        Lead.objects.create(
            exhibitor=exhibitor,
            exhibitor_name=exhibitor.name,
            pseudonymization_id='old123',
            scanned=old_date,
            scan_type='manual',
            device_name='test-device',
            booth_id=exhibitor.booth_id,
            booth_name=exhibitor.booth_name
        )
        
        # Create a recent lead
        Lead.objects.create(
            exhibitor=exhibitor,
            exhibitor_name=exhibitor.name,
            pseudonymization_id='recent123',
            scanned=timezone.now(),
            scan_type='manual',
            device_name='test-device',
            booth_id=exhibitor.booth_id,
            booth_name=exhibitor.booth_name
        )
        
        self.assertEqual(exhibitor.recent_leads_count, 1)
    
    def test_regenerate_key(self):
        """Test key regeneration."""
        exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='Test Exhibitor',
            booth_name='Booth A1'
        )
        
        old_key = exhibitor.key
        
        with patch('eventyay.plugins.exhibitor.services.ExhibitorKeyService.regenerate_key') as mock_regen:
            mock_regen.return_value = 'newkey12'
            new_key = exhibitor.regenerate_key()
            
            self.assertEqual(new_key, 'newkey12')
            mock_regen.assert_called_once_with(exhibitor)


class ExhibitorSettingsModelTest(TestCase):
    """Test cases for ExhibitorSettings model."""
    
    def setUp(self):
        """Set up test data."""
        self.organizer = Organizer.objects.create(
            name='Test Organizer',
            slug='test-org'
        )
        self.event = Event.objects.create(
            name='Test Event',
            slug='test-event',
            organizer=self.organizer,
            date_from=timezone.now(),
            date_to=timezone.now() + timezone.timedelta(days=1)
        )
    
    def test_settings_creation(self):
        """Test settings creation with defaults."""
        settings = ExhibitorSettings.objects.create(event=self.event)
        
        self.assertEqual(settings.event, self.event)
        self.assertTrue(settings.enable_public_directory)
        self.assertTrue(settings.enable_lead_export)
        self.assertEqual(settings.lead_retention_days, 365)
        self.assertEqual(settings.allowed_fields, [])
    
    def test_all_allowed_fields_property(self):
        """Test all_allowed_fields property."""
        settings = ExhibitorSettings.objects.create(
            event=self.event,
            allowed_fields=['attendee_city', 'attendee_company']
        )
        
        all_fields = settings.all_allowed_fields
        self.assertIn('attendee_name', all_fields)
        self.assertIn('attendee_email', all_fields)
        self.assertIn('attendee_city', all_fields)
        self.assertIn('attendee_company', all_fields)
        self.assertEqual(len(all_fields), 4)


class LeadModelTest(TestCase):
    """Test cases for Lead model."""
    
    def setUp(self):
        """Set up test data."""
        self.organizer = Organizer.objects.create(
            name='Test Organizer',
            slug='test-org'
        )
        self.event = Event.objects.create(
            name='Test Event',
            slug='test-event',
            organizer=self.organizer,
            date_from=timezone.now(),
            date_to=timezone.now() + timezone.timedelta(days=1)
        )
        self.exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='Test Exhibitor',
            booth_name='Booth A1'
        )
    
    def test_lead_creation(self):
        """Test basic lead creation."""
        attendee_data = {
            'name': 'John Doe',
            'email': 'john@example.com'
        }
        
        lead = Lead.objects.create(
            exhibitor=self.exhibitor,
            exhibitor_name=self.exhibitor.name,
            pseudonymization_id='test123',
            scanned=timezone.now(),
            scan_type='qr',
            device_name='tablet-01',
            booth_id=self.exhibitor.booth_id,
            booth_name=self.exhibitor.booth_name,
            attendee=attendee_data
        )
        
        self.assertEqual(lead.exhibitor, self.exhibitor)
        self.assertEqual(lead.pseudonymization_id, 'test123')
        self.assertEqual(lead.scan_type, 'qr')
        self.assertEqual(lead.follow_up_status, 'pending')
        self.assertEqual(lead.attendee, attendee_data)
    
    def test_lead_uniqueness(self):
        """Test that leads are unique per exhibitor and attendee."""
        Lead.objects.create(
            exhibitor=self.exhibitor,
            exhibitor_name=self.exhibitor.name,
            pseudonymization_id='test123',
            scanned=timezone.now(),
            scan_type='qr',
            device_name='tablet-01',
            booth_id=self.exhibitor.booth_id,
            booth_name=self.exhibitor.booth_name
        )
        
        # Try to create duplicate
        with self.assertRaises(Exception):  # Should raise IntegrityError
            Lead.objects.create(
                exhibitor=self.exhibitor,
                exhibitor_name=self.exhibitor.name,
                pseudonymization_id='test123',  # Same ID
                scanned=timezone.now(),
                scan_type='manual',
                device_name='tablet-02',
                booth_id=self.exhibitor.booth_id,
                booth_name=self.exhibitor.booth_name
            )
    
    def test_get_attendee_name(self):
        """Test get_attendee_name method."""
        # Test with attendee data
        lead = Lead.objects.create(
            exhibitor=self.exhibitor,
            exhibitor_name=self.exhibitor.name,
            pseudonymization_id='test123',
            scanned=timezone.now(),
            scan_type='qr',
            device_name='tablet-01',
            booth_id=self.exhibitor.booth_id,
            booth_name=self.exhibitor.booth_name,
            attendee={'name': 'John Doe', 'email': 'john@example.com'}
        )
        
        self.assertEqual(lead.get_attendee_name(), 'John Doe')
        
        # Test without attendee data
        lead_no_data = Lead.objects.create(
            exhibitor=self.exhibitor,
            exhibitor_name=self.exhibitor.name,
            pseudonymization_id='test456',
            scanned=timezone.now(),
            scan_type='manual',
            device_name='tablet-01',
            booth_id=self.exhibitor.booth_id,
            booth_name=self.exhibitor.booth_name
        )
        
        self.assertEqual(lead_no_data.get_attendee_name(), 'Attendee test456')
    
    def test_get_attendee_email(self):
        """Test get_attendee_email method."""
        lead = Lead.objects.create(
            exhibitor=self.exhibitor,
            exhibitor_name=self.exhibitor.name,
            pseudonymization_id='test123',
            scanned=timezone.now(),
            scan_type='qr',
            device_name='tablet-01',
            booth_id=self.exhibitor.booth_id,
            booth_name=self.exhibitor.booth_name,
            attendee={'name': 'John Doe', 'email': 'john@example.com'}
        )
        
        self.assertEqual(lead.get_attendee_email(), 'john@example.com')
        
        # Test without email
        lead_no_email = Lead.objects.create(
            exhibitor=self.exhibitor,
            exhibitor_name=self.exhibitor.name,
            pseudonymization_id='test456',
            scanned=timezone.now(),
            scan_type='manual',
            device_name='tablet-01',
            booth_id=self.exhibitor.booth_id,
            booth_name=self.exhibitor.booth_name,
            attendee={'name': 'Jane Doe'}
        )
        
        self.assertIsNone(lead_no_email.get_attendee_email())
    
    def test_update_follow_up_status(self):
        """Test update_follow_up_status method."""
        lead = Lead.objects.create(
            exhibitor=self.exhibitor,
            exhibitor_name=self.exhibitor.name,
            pseudonymization_id='test123',
            scanned=timezone.now(),
            scan_type='qr',
            device_name='tablet-01',
            booth_id=self.exhibitor.booth_id,
            booth_name=self.exhibitor.booth_name
        )
        
        self.assertEqual(lead.follow_up_status, 'pending')
        self.assertIsNone(lead.follow_up_date)
        
        lead.update_follow_up_status('contacted', 'Called customer')
        
        lead.refresh_from_db()
        self.assertEqual(lead.follow_up_status, 'contacted')
        self.assertEqual(lead.notes, 'Called customer')
        self.assertIsNotNone(lead.follow_up_date)


class ExhibitorTagModelTest(TestCase):
    """Test cases for ExhibitorTag model."""
    
    def setUp(self):
        """Set up test data."""
        self.organizer = Organizer.objects.create(
            name='Test Organizer',
            slug='test-org'
        )
        self.event = Event.objects.create(
            name='Test Event',
            slug='test-event',
            organizer=self.organizer,
            date_from=timezone.now(),
            date_to=timezone.now() + timezone.timedelta(days=1)
        )
        self.exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='Test Exhibitor',
            booth_name='Booth A1'
        )
    
    def test_tag_creation(self):
        """Test tag creation."""
        tag = ExhibitorTag.objects.create(
            exhibitor=self.exhibitor,
            name='technology'
        )
        
        self.assertEqual(tag.exhibitor, self.exhibitor)
        self.assertEqual(tag.name, 'technology')
        self.assertEqual(tag.use_count, 0)
    
    def test_tag_uniqueness(self):
        """Test that tags are unique per exhibitor."""
        ExhibitorTag.objects.create(
            exhibitor=self.exhibitor,
            name='technology'
        )
        
        # Try to create duplicate
        with self.assertRaises(Exception):  # Should raise IntegrityError
            ExhibitorTag.objects.create(
                exhibitor=self.exhibitor,
                name='technology'  # Same name
            )
    
    def test_increment_usage(self):
        """Test increment_usage method."""
        tag = ExhibitorTag.objects.create(
            exhibitor=self.exhibitor,
            name='technology'
        )
        
        self.assertEqual(tag.use_count, 0)
        
        tag.increment_usage()
        tag.refresh_from_db()
        
        self.assertEqual(tag.use_count, 1)


class ExhibitorItemModelTest(TestCase):
    """Test cases for ExhibitorItem model."""
    
    def setUp(self):
        """Set up test data."""
        self.organizer = Organizer.objects.create(
            name='Test Organizer',
            slug='test-org'
        )
        self.event = Event.objects.create(
            name='Test Event',
            slug='test-event',
            organizer=self.organizer,
            date_from=timezone.now(),
            date_to=timezone.now() + timezone.timedelta(days=1)
        )
        self.exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='Test Exhibitor',
            booth_name='Booth A1'
        )
    
    def test_exhibitor_item_creation(self):
        """Test exhibitor item assignment creation."""
        # This test would need the actual Item model from eventyay
        # For now, test basic creation without item
        exhibitor_item = ExhibitorItem.objects.create(
            exhibitor=self.exhibitor
        )
        
        self.assertEqual(exhibitor_item.exhibitor, self.exhibitor)
        self.assertIsNone(exhibitor_item.item)