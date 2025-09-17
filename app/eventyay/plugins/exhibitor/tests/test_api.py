"""
Tests for exhibitor API functionality.
"""

import json
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from eventyay.base.models import Event, Organizer, User
from ..models import ExhibitorInfo, ExhibitorSettings, Lead, ExhibitorTag


class ExhibitorAuthAPITest(APITestCase):
    """Test cases for exhibitor authentication API."""
    
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
            booth_name='Booth A1',
            key='testkey1',
            lead_scanning_enabled=True
        )
        
        self.client = APIClient()
    
    def test_successful_authentication(self):
        """Test successful exhibitor authentication."""
        url = reverse('plugins:exhibitor:api-auth', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        data = {'key': 'testkey1'}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['exhibitor_id'], self.exhibitor.id)
        self.assertEqual(response.data['exhibitor_name'], self.exhibitor.name)
        self.assertEqual(response.data['booth_id'], self.exhibitor.booth_id)
        self.assertEqual(response.data['booth_name'], self.exhibitor.booth_name)
        self.assertTrue(response.data['lead_scanning_enabled'])
    
    def test_invalid_key_authentication(self):
        """Test authentication with invalid key."""
        url = reverse('plugins:exhibitor:api-auth', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        data = {'key': 'invalidkey'}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error'], 'Invalid credentials')
    
    def test_missing_key_authentication(self):
        """Test authentication with missing key."""
        url = reverse('plugins:exhibitor:api-auth', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        data = {}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data['success'])
    
    def test_inactive_exhibitor_authentication(self):
        """Test authentication with inactive exhibitor."""
        self.exhibitor.is_active = False
        self.exhibitor.save()
        
        url = reverse('plugins:exhibitor:api-auth', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        data = {'key': 'testkey1'}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data['success'])


class ExhibitorListAPITest(APITestCase):
    """Test cases for exhibitor list API."""
    
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
        
        # Create test exhibitors
        self.exhibitor1 = ExhibitorInfo.objects.create(
            event=self.event,
            name='Tech Corp',
            description='Technology company',
            booth_name='Booth A1',
            featured=True,
            sort_order=1
        )
        
        self.exhibitor2 = ExhibitorInfo.objects.create(
            event=self.event,
            name='Design Studio',
            description='Creative design services',
            booth_name='Booth B1',
            featured=False,
            sort_order=2
        )
        
        self.exhibitor3 = ExhibitorInfo.objects.create(
            event=self.event,
            name='Marketing Agency',
            description='Digital marketing solutions',
            booth_name='Booth C1',
            featured=True,
            sort_order=3,
            is_active=False  # Inactive
        )
        
        self.client = APIClient()
    
    def test_list_all_exhibitors(self):
        """Test listing all active exhibitors."""
        url = reverse('plugins:exhibitor:api-exhibitors', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 2)  # Only active exhibitors
        
        exhibitor_names = [e['name'] for e in response.data['exhibitors']]
        self.assertIn('Tech Corp', exhibitor_names)
        self.assertIn('Design Studio', exhibitor_names)
        self.assertNotIn('Marketing Agency', exhibitor_names)  # Inactive
    
    def test_list_featured_exhibitors(self):
        """Test listing only featured exhibitors."""
        url = reverse('plugins:exhibitor:api-exhibitors', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        response = self.client.get(url, {'featured': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 1)  # Only featured and active
        self.assertEqual(response.data['exhibitors'][0]['name'], 'Tech Corp')
    
    def test_search_exhibitors(self):
        """Test searching exhibitors."""
        url = reverse('plugins:exhibitor:api-exhibitors', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        response = self.client.get(url, {'search': 'design'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['exhibitors'][0]['name'], 'Design Studio')
    
    def test_exhibitor_ordering(self):
        """Test that exhibitors are ordered correctly."""
        url = reverse('plugins:exhibitor:api-exhibitors', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        exhibitor_names = [e['name'] for e in response.data['exhibitors']]
        self.assertEqual(exhibitor_names, ['Tech Corp', 'Design Studio'])  # Ordered by sort_order


class ExhibitorDetailAPITest(APITestCase):
    """Test cases for exhibitor detail API."""
    
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
            description='Test description',
            booth_name='Booth A1',
            url='https://example.com',
            email='test@example.com'
        )
        
        self.client = APIClient()
    
    def test_get_exhibitor_detail(self):
        """Test getting exhibitor details."""
        url = reverse('plugins:exhibitor:api-exhibitor-detail', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug,
            'pk': self.exhibitor.pk
        })
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        exhibitor_data = response.data['exhibitor']
        self.assertEqual(exhibitor_data['name'], 'Test Exhibitor')
        self.assertEqual(exhibitor_data['description'], 'Test description')
        self.assertEqual(exhibitor_data['booth_name'], 'Booth A1')
        self.assertEqual(exhibitor_data['url'], 'https://example.com')
    
    def test_get_nonexistent_exhibitor(self):
        """Test getting details for non-existent exhibitor."""
        url = reverse('plugins:exhibitor:api-exhibitor-detail', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug,
            'pk': 99999
        })
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error'], 'Exhibitor not found')
    
    def test_get_inactive_exhibitor(self):
        """Test getting details for inactive exhibitor."""
        self.exhibitor.is_active = False
        self.exhibitor.save()
        
        url = reverse('plugins:exhibitor:api-exhibitor-detail', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug,
            'pk': self.exhibitor.pk
        })
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.data['success'])


class LeadAPITest(APITestCase):
    """Test cases for lead management API."""
    
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
            booth_name='Booth A1',
            key='testkey1',
            lead_scanning_enabled=True
        )
        
        # Create exhibitor settings
        self.settings = ExhibitorSettings.objects.create(
            event=self.event,
            allowed_fields=['attendee_city', 'attendee_company']
        )
        
        # Create test leads
        self.lead1 = Lead.objects.create(
            exhibitor=self.exhibitor,
            exhibitor_name=self.exhibitor.name,
            pseudonymization_id='lead001',
            scanned=timezone.now(),
            scan_type='qr',
            device_name='tablet-01',
            booth_id=self.exhibitor.booth_id,
            booth_name=self.exhibitor.booth_name,
            attendee={'name': 'John Doe', 'email': 'john@example.com'},
            follow_up_status='pending'
        )
        
        self.lead2 = Lead.objects.create(
            exhibitor=self.exhibitor,
            exhibitor_name=self.exhibitor.name,
            pseudonymization_id='lead002',
            scanned=timezone.now() - timezone.timedelta(hours=1),
            scan_type='manual',
            device_name='tablet-01',
            booth_id=self.exhibitor.booth_id,
            booth_name=self.exhibitor.booth_name,
            attendee={'name': 'Jane Smith', 'email': 'jane@example.com'},
            follow_up_status='contacted'
        )
        
        self.client = APIClient()
    
    def test_retrieve_leads_with_valid_key(self):
        """Test retrieving leads with valid exhibitor key."""
        url = reverse('plugins:exhibitor:api-lead-list', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        response = self.client.get(url, HTTP_EXHIBITOR_KEY='testkey1')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['leads']), 2)
        
        # Check lead data
        lead_names = [lead['attendee_name'] for lead in response.data['leads']]
        self.assertIn('John Doe', lead_names)
        self.assertIn('Jane Smith', lead_names)
    
    def test_retrieve_leads_with_invalid_key(self):
        """Test retrieving leads with invalid exhibitor key."""
        url = reverse('plugins:exhibitor:api-lead-list', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        response = self.client.get(url, HTTP_EXHIBITOR_KEY='invalidkey')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_retrieve_leads_without_key(self):
        """Test retrieving leads without exhibitor key."""
        url = reverse('plugins:exhibitor:api-lead-list', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_retrieve_leads_with_status_filter(self):
        """Test retrieving leads with status filter."""
        url = reverse('plugins:exhibitor:api-lead-list', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        response = self.client.get(
            url, 
            {'status': 'contacted'}, 
            HTTP_EXHIBITOR_KEY='testkey1'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['leads'][0]['attendee_name'], 'Jane Smith')
    
    def test_retrieve_leads_with_search(self):
        """Test retrieving leads with search filter."""
        url = reverse('plugins:exhibitor:api-lead-list', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        response = self.client.get(
            url, 
            {'search': 'john'}, 
            HTTP_EXHIBITOR_KEY='testkey1'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['leads'][0]['attendee_name'], 'John Doe')
    
    def test_update_lead_notes(self):
        """Test updating lead notes."""
        url = reverse('plugins:exhibitor:api-lead-update', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug,
            'lead_id': 'lead001'
        })
        
        data = {
            'note': 'Very interested in our product',
            'tags': ['hot-lead', 'enterprise']
        }
        
        response = self.client.post(
            url, 
            data, 
            format='json',
            HTTP_EXHIBITOR_KEY='testkey1'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Verify lead was updated
        self.lead1.refresh_from_db()
        self.assertEqual(self.lead1.attendee['note'], 'Very interested in our product')
        self.assertIn('hot-lead', self.lead1.attendee['tags'])
        self.assertIn('enterprise', self.lead1.attendee['tags'])
    
    def test_update_lead_follow_up_status(self):
        """Test updating lead follow-up status."""
        url = reverse('plugins:exhibitor:api-lead-update', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug,
            'lead_id': 'lead001'
        })
        
        data = {'follow_up_status': 'qualified'}
        
        response = self.client.post(
            url, 
            data, 
            format='json',
            HTTP_EXHIBITOR_KEY='testkey1'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Verify lead was updated
        self.lead1.refresh_from_db()
        self.assertEqual(self.lead1.follow_up_status, 'qualified')
        self.assertIsNotNone(self.lead1.follow_up_date)
    
    def test_update_nonexistent_lead(self):
        """Test updating non-existent lead."""
        url = reverse('plugins:exhibitor:api-lead-update', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug,
            'lead_id': 'nonexistent'
        })
        
        data = {'note': 'Test note'}
        
        response = self.client.post(
            url, 
            data, 
            format='json',
            HTTP_EXHIBITOR_KEY='testkey1'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error'], 'Lead not found')


class TagAPITest(APITestCase):
    """Test cases for tag management API."""
    
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
            booth_name='Booth A1',
            key='testkey1'
        )
        
        # Create test tags
        self.tag1 = ExhibitorTag.objects.create(
            exhibitor=self.exhibitor,
            name='hot-lead',
            use_count=5
        )
        
        self.tag2 = ExhibitorTag.objects.create(
            exhibitor=self.exhibitor,
            name='enterprise',
            use_count=2
        )
        
        self.client = APIClient()
    
    def test_list_tags(self):
        """Test listing exhibitor tags."""
        url = reverse('plugins:exhibitor:api-tags', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        response = self.client.get(url, HTTP_EXHIBITOR_KEY='testkey1')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(len(response.data['tags']), 2)
        self.assertIn('hot-lead', response.data['tags'])
        self.assertIn('enterprise', response.data['tags'])
        
        # Check that tags are ordered by use_count (descending)
        self.assertEqual(response.data['tags'][0], 'hot-lead')  # Higher use_count
        self.assertEqual(response.data['tags'][1], 'enterprise')
    
    def test_list_tags_with_invalid_key(self):
        """Test listing tags with invalid exhibitor key."""
        url = reverse('plugins:exhibitor:api-tags', kwargs={
            'organizer': self.organizer.slug,
            'event': self.event.slug
        })
        
        response = self.client.get(url, HTTP_EXHIBITOR_KEY='invalidkey')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)