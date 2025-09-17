"""
Management command to rollback exhibitor migration and restore legacy system.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings

from eventyay.plugins.exhibitor.models import (
    ExhibitorInfo, ExhibitorSettings, Lead, ExhibitorTag, ExhibitorItem
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Command to rollback exhibitor migration."""
    
    help = 'Rollback exhibitor migration and restore legacy system'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm that you want to rollback the migration (required)'
        )
        parser.add_argument(
            '--backup-data',
            action='store_true',
            help='Create backup of current data before rollback'
        )
        parser.add_argument(
            '--event-slug',
            type=str,
            help='Rollback data for specific event only'
        )
    
    def handle(self, *args, **options):
        """Execute the rollback command."""
        if not options.get('confirm'):
            raise CommandError(
                'This command will delete all exhibitor data. '
                'Use --confirm to proceed.'
            )
        
        self.backup_data = options.get('backup_data', False)
        self.event_slug = options.get('event_slug')
        
        self.stdout.write(
            self.style.WARNING('Starting exhibitor migration rollback...')
        )
        
        try:
            with transaction.atomic():
                if self.backup_data:
                    self.create_backup()
                
                self.rollback_migration()
                
            self.stdout.write(
                self.style.SUCCESS('✓ Exhibitor migration rollback completed!')
            )
            
        except Exception as e:
            logger.exception("Error during rollback")
            raise CommandError(f'Rollback failed: {str(e)}')
    
    def create_backup(self):
        """Create backup of current exhibitor data."""
        self.stdout.write('Creating data backup...')
        
        import json
        from datetime import datetime
        
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'exhibitors': [],
            'settings': [],
            'leads': [],
            'tags': [],
            'items': []
        }
        
        # Backup exhibitors
        queryset = ExhibitorInfo.objects.all()
        if self.event_slug:
            queryset = queryset.filter(event__slug=self.event_slug)
        
        for exhibitor in queryset:
            backup_data['exhibitors'].append({
                'id': exhibitor.id,
                'event_id': exhibitor.event_id,
                'name': exhibitor.name,
                'description': exhibitor.description,
                'url': exhibitor.url,
                'email': exhibitor.email,
                'logo': exhibitor.logo.name if exhibitor.logo else None,
                'key': exhibitor.key,
                'booth_id': exhibitor.booth_id,
                'booth_name': exhibitor.booth_name,
                'lead_scanning_enabled': exhibitor.lead_scanning_enabled,
                'allow_voucher_access': exhibitor.allow_voucher_access,
                'allow_lead_access': exhibitor.allow_lead_access,
                'lead_scanning_scope_by_device': exhibitor.lead_scanning_scope_by_device,
                'is_active': exhibitor.is_active,
                'sort_order': exhibitor.sort_order,
                'featured': exhibitor.featured,
                'created': exhibitor.created.isoformat(),
                'modified': exhibitor.modified.isoformat(),
            })
        
        # Backup settings
        settings_queryset = ExhibitorSettings.objects.all()
        if self.event_slug:
            settings_queryset = settings_queryset.filter(event__slug=self.event_slug)
        
        for setting in settings_queryset:
            backup_data['settings'].append({
                'id': setting.id,
                'event_id': setting.event_id,
                'exhibitors_access_mail_subject': setting.exhibitors_access_mail_subject,
                'exhibitors_access_mail_body': setting.exhibitors_access_mail_body,
                'allowed_fields': setting.allowed_fields,
                'enable_public_directory': setting.enable_public_directory,
                'enable_lead_export': setting.enable_lead_export,
                'lead_retention_days': setting.lead_retention_days,
            })
        
        # Backup leads
        leads_queryset = Lead.objects.all()
        if self.event_slug:
            leads_queryset = leads_queryset.filter(exhibitor__event__slug=self.event_slug)
        
        for lead in leads_queryset:
            backup_data['leads'].append({
                'id': lead.id,
                'exhibitor_id': lead.exhibitor_id,
                'exhibitor_name': lead.exhibitor_name,
                'pseudonymization_id': lead.pseudonymization_id,
                'scanned': lead.scanned.isoformat(),
                'scan_type': lead.scan_type,
                'device_name': lead.device_name,
                'attendee': lead.attendee,
                'booth_id': lead.booth_id,
                'booth_name': lead.booth_name,
                'notes': lead.notes,
                'follow_up_status': lead.follow_up_status,
                'follow_up_date': lead.follow_up_date.isoformat() if lead.follow_up_date else None,
            })
        
        # Backup tags
        tags_queryset = ExhibitorTag.objects.all()
        if self.event_slug:
            tags_queryset = tags_queryset.filter(exhibitor__event__slug=self.event_slug)
        
        for tag in tags_queryset:
            backup_data['tags'].append({
                'id': tag.id,
                'exhibitor_id': tag.exhibitor_id,
                'name': tag.name,
                'use_count': tag.use_count,
            })
        
        # Backup item assignments
        items_queryset = ExhibitorItem.objects.all()
        if self.event_slug:
            items_queryset = items_queryset.filter(exhibitor__event__slug=self.event_slug)
        
        for item in items_queryset:
            backup_data['items'].append({
                'id': item.id,
                'exhibitor_id': item.exhibitor_id,
                'item_id': item.item_id,
            })
        
        # Save backup to file
        backup_filename = f'exhibitor_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        backup_path = f'/tmp/{backup_filename}'
        
        with open(backup_path, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ Backup created: {backup_path}')
        )
    
    def rollback_migration(self):
        """Rollback the exhibitor migration."""
        self.stdout.write('Rolling back exhibitor migration...')
        
        # Delete in reverse dependency order
        if self.event_slug:
            # Delete for specific event
            self.stdout.write(f'Rolling back data for event: {self.event_slug}')
            
            # Delete item assignments
            deleted_items = ExhibitorItem.objects.filter(
                exhibitor__event__slug=self.event_slug
            ).delete()
            self.stdout.write(f'  Deleted {deleted_items[0]} item assignments')
            
            # Delete tags
            deleted_tags = ExhibitorTag.objects.filter(
                exhibitor__event__slug=self.event_slug
            ).delete()
            self.stdout.write(f'  Deleted {deleted_tags[0]} tags')
            
            # Delete leads
            deleted_leads = Lead.objects.filter(
                exhibitor__event__slug=self.event_slug
            ).delete()
            self.stdout.write(f'  Deleted {deleted_leads[0]} leads')
            
            # Delete exhibitors
            deleted_exhibitors = ExhibitorInfo.objects.filter(
                event__slug=self.event_slug
            ).delete()
            self.stdout.write(f'  Deleted {deleted_exhibitors[0]} exhibitors')
            
            # Delete settings
            deleted_settings = ExhibitorSettings.objects.filter(
                event__slug=self.event_slug
            ).delete()
            self.stdout.write(f'  Deleted {deleted_settings[0]} settings')
            
        else:
            # Delete all exhibitor data
            self.stdout.write('Rolling back all exhibitor data')
            
            # Delete item assignments
            deleted_items = ExhibitorItem.objects.all().delete()
            self.stdout.write(f'  Deleted {deleted_items[0]} item assignments')
            
            # Delete tags
            deleted_tags = ExhibitorTag.objects.all().delete()
            self.stdout.write(f'  Deleted {deleted_tags[0]} tags')
            
            # Delete leads
            deleted_leads = Lead.objects.all().delete()
            self.stdout.write(f'  Deleted {deleted_leads[0]} leads')
            
            # Delete exhibitors
            deleted_exhibitors = ExhibitorInfo.objects.all().delete()
            self.stdout.write(f'  Deleted {deleted_exhibitors[0]} exhibitors')
            
            # Delete settings
            deleted_settings = ExhibitorSettings.objects.all().delete()
            self.stdout.write(f'  Deleted {deleted_settings[0]} settings')
        
        self.stdout.write('Migration rollback completed')
        
        # Instructions for restoring legacy system
        self.stdout.write('\n' + '='*60)
        self.stdout.write('NEXT STEPS:')
        self.stdout.write('='*60)
        self.stdout.write('1. Remove exhibitor plugin from INSTALLED_APPS')
        self.stdout.write('2. Run: python manage.py migrate exhibitor zero')
        self.stdout.write('3. Restore legacy exhibitor system if needed')
        self.stdout.write('4. Restore data from backup if created')
        self.stdout.write('='*60)