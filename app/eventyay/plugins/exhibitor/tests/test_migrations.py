"""
Tests for exhibitor migration functionality.
"""

import json
import tempfile
from django.test import TestCase, TransactionTestCase
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from io import StringIO

from eventyay.base.models import Event, Organizer
from ..models import ExhibitorInfo, ExhibitorSettings, Lead, ExhibitorTag


class MigrationTestCase(TransactionTestCase):
    """Test cases for exhibitor migrations."""
    
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
    
    def test_initial_migration(self):
        """Test that initial migration creates tables correctly."""
        # Check that tables exist
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'exhibitor_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = [
            'exhibitor_exhibitorinfo',
            'exhibitor_exhibitorsettings',
            'exhibitor_lead',
            'exhibitor_exhibitortag',
            'exhibitor_exhibitoritem'
        ]
        
        for table in expected_tables:
            self.assertIn(table, tables, f"Table {table} should exist after migration")
    
    def test_data_validation_command(self):
        """Test the data validation management command."""
        # Create test data
        exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='Test Exhibitor',
            booth_name='Booth A1'
        )
        
        ExhibitorSettings.objects.create(
            event=self.event,
            allowed_fields=['attendee_city']
        )
        
        Lead.objects.create(
            exhibitor=exhibitor,
            exhibitor_name=exhibitor.name,
            pseudonymization_id='test123',
            scanned=timezone.now(),
            scan_type='qr',
            device_name='tablet-01',
            booth_id=exhibitor.booth_id,
            booth_name=exhibitor.booth_name
        )
        
        # Run validation command
        out = StringIO()
        call_command('validate_exhibitor_data', stdout=out, verbosity=2)
        output = out.getvalue()
        
        # Check that validation passed
        self.assertIn('All exhibitor data validation passed', output)
        self.assertIn('EXHIBITORS:', output)
        self.assertIn('Valid: 1', output)
    
    def test_data_validation_with_errors(self):
        """Test data validation command with invalid data."""
        # Create exhibitor with invalid data
        exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='A',  # Too short
            booth_name='Booth A1'
        )
        
        # Create lead with invalid status
        lead = Lead.objects.create(
            exhibitor=exhibitor,
            exhibitor_name=exhibitor.name,
            pseudonymization_id='test123',
            scanned=timezone.now(),
            scan_type='qr',
            device_name='tablet-01',
            booth_id=exhibitor.booth_id,
            booth_name=exhibitor.booth_name,
            follow_up_status='invalid_status'  # Invalid status
        )
        
        # Run validation command
        out = StringIO()
        call_command('validate_exhibitor_data', stdout=out, verbosity=2)
        output = out.getvalue()
        
        # Check that validation found errors
        self.assertIn('validation errors', output)
        self.assertIn('Name too short', output)
        self.assertIn('Invalid follow-up status', output)
    
    def test_rollback_command_without_confirm(self):
        """Test that rollback command requires confirmation."""
        out = StringIO()
        
        with self.assertRaises(Exception):
            call_command('rollback_exhibitor_migration', stdout=out)
    
    def test_rollback_command_with_backup(self):
        """Test rollback command with backup creation."""
        # Create test data
        exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='Test Exhibitor',
            booth_name='Booth A1'
        )
        
        settings = ExhibitorSettings.objects.create(
            event=self.event,
            allowed_fields=['attendee_city']
        )
        
        lead = Lead.objects.create(
            exhibitor=exhibitor,
            exhibitor_name=exhibitor.name,
            pseudonymization_id='test123',
            scanned=timezone.now(),
            scan_type='qr',
            device_name='tablet-01',
            booth_id=exhibitor.booth_id,
            booth_name=exhibitor.booth_name
        )
        
        tag = ExhibitorTag.objects.create(
            exhibitor=exhibitor,
            name='technology'
        )
        
        # Verify data exists
        self.assertEqual(ExhibitorInfo.objects.count(), 1)
        self.assertEqual(ExhibitorSettings.objects.count(), 1)
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(ExhibitorTag.objects.count(), 1)
        
        # Run rollback command with backup
        out = StringIO()
        call_command(
            'rollback_exhibitor_migration',
            '--confirm',
            '--backup-data',
            stdout=out
        )
        output = out.getvalue()
        
        # Check that backup was created
        self.assertIn('Backup created:', output)
        
        # Check that data was deleted
        self.assertEqual(ExhibitorInfo.objects.count(), 0)
        self.assertEqual(ExhibitorSettings.objects.count(), 0)
        self.assertEqual(Lead.objects.count(), 0)
        self.assertEqual(ExhibitorTag.objects.count(), 0)
    
    def test_rollback_command_specific_event(self):
        """Test rollback command for specific event only."""
        # Create data for two events
        event2 = Event.objects.create(
            name='Test Event 2',
            slug='test-event-2',
            organizer=self.organizer,
            date_from=timezone.now(),
            date_to=timezone.now() + timezone.timedelta(days=1)
        )
        
        exhibitor1 = ExhibitorInfo.objects.create(
            event=self.event,
            name='Exhibitor 1',
            booth_name='Booth A1'
        )
        
        exhibitor2 = ExhibitorInfo.objects.create(
            event=event2,
            name='Exhibitor 2',
            booth_name='Booth B1'
        )
        
        # Verify both exist
        self.assertEqual(ExhibitorInfo.objects.count(), 2)
        
        # Run rollback for specific event
        out = StringIO()
        call_command(
            'rollback_exhibitor_migration',
            '--confirm',
            '--event-slug', 'test-event',
            stdout=out
        )
        
        # Check that only one event's data was deleted
        self.assertEqual(ExhibitorInfo.objects.count(), 1)
        self.assertEqual(ExhibitorInfo.objects.first().event, event2)


class DataIntegrityTestCase(TestCase):
    """Test cases for data integrity during migration."""
    
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
    
    def test_unique_constraints(self):
        """Test that unique constraints are enforced."""
        # Create first exhibitor
        exhibitor1 = ExhibitorInfo.objects.create(
            event=self.event,
            name='Exhibitor 1',
            booth_name='Booth A1',
            booth_id='BOOTH001'
        )
        
        # Try to create second exhibitor with same booth_id
        with self.assertRaises(Exception):
            ExhibitorInfo.objects.create(
                event=self.event,
                name='Exhibitor 2',
                booth_name='Booth A2',
                booth_id='BOOTH001'  # Duplicate
            )
    
    def test_foreign_key_constraints(self):
        """Test that foreign key constraints are enforced."""
        exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='Test Exhibitor',
            booth_name='Booth A1'
        )
        
        # Create lead
        lead = Lead.objects.create(
            exhibitor=exhibitor,
            exhibitor_name=exhibitor.name,
            pseudonymization_id='test123',
            scanned=timezone.now(),
            scan_type='qr',
            device_name='tablet-01',
            booth_id=exhibitor.booth_id,
            booth_name=exhibitor.booth_name
        )
        
        # Verify relationship
        self.assertEqual(lead.exhibitor, exhibitor)
        self.assertEqual(exhibitor.leads.count(), 1)
    
    def test_cascade_deletion(self):
        """Test that cascade deletion works correctly."""
        exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='Test Exhibitor',
            booth_name='Booth A1'
        )
        
        # Create related objects
        lead = Lead.objects.create(
            exhibitor=exhibitor,
            exhibitor_name=exhibitor.name,
            pseudonymization_id='test123',
            scanned=timezone.now(),
            scan_type='qr',
            device_name='tablet-01',
            booth_id=exhibitor.booth_id,
            booth_name=exhibitor.booth_name
        )
        
        tag = ExhibitorTag.objects.create(
            exhibitor=exhibitor,
            name='technology'
        )
        
        # Verify objects exist
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(ExhibitorTag.objects.count(), 1)
        
        # Delete exhibitor
        exhibitor.delete()
        
        # Verify related objects were deleted
        self.assertEqual(Lead.objects.count(), 0)
        self.assertEqual(ExhibitorTag.objects.count(), 0)
    
    def test_json_field_integrity(self):
        """Test that JSON fields maintain data integrity."""
        exhibitor = ExhibitorInfo.objects.create(
            event=self.event,
            name='Test Exhibitor',
            booth_name='Booth A1'
        )
        
        # Create lead with JSON attendee data
        attendee_data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'company': 'Test Corp',
            'tags': ['vip', 'interested']
        }
        
        lead = Lead.objects.create(
            exhibitor=exhibitor,
            exhibitor_name=exhibitor.name,
            pseudonymization_id='test123',
            scanned=timezone.now(),
            scan_type='qr',
            device_name='tablet-01',
            booth_id=exhibitor.booth_id,
            booth_name=exhibitor.booth_name,
            attendee=attendee_data
        )
        
        # Retrieve and verify JSON data
        lead.refresh_from_db()
        self.assertEqual(lead.attendee['name'], 'John Doe')
        self.assertEqual(lead.attendee['email'], 'john@example.com')
        self.assertEqual(lead.attendee['company'], 'Test Corp')
        self.assertIn('vip', lead.attendee['tags'])
        self.assertIn('interested', lead.attendee['tags'])