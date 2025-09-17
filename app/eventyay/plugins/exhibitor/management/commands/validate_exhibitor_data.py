"""
Management command to validate exhibitor data integrity after migration.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.core.exceptions import ValidationError

from eventyay.plugins.exhibitor.models import (
    ExhibitorInfo, ExhibitorSettings, Lead, ExhibitorTag, ExhibitorItem
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Command to validate exhibitor data integrity."""
    
    help = 'Validate exhibitor data integrity after migration'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--event-slug',
            type=str,
            help='Validate data for specific event only'
        )
        parser.add_argument(
            '--fix-issues',
            action='store_true',
            help='Attempt to fix validation issues automatically'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed validation results'
        )
    
    def handle(self, *args, **options):
        """Execute the validation command."""
        self.verbosity = options.get('verbosity', 1)
        self.verbose = options.get('verbose', False)
        self.fix_issues = options.get('fix_issues', False)
        self.event_slug = options.get('event_slug')
        
        self.stdout.write(
            self.style.SUCCESS('Starting exhibitor data validation...')
        )
        
        try:
            validation_results = self.validate_all_data()
            self.display_results(validation_results)
            
            if validation_results['total_errors'] == 0:
                self.stdout.write(
                    self.style.SUCCESS('✓ All exhibitor data validation passed!')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Found {validation_results["total_errors"]} validation errors'
                    )
                )
                if not self.fix_issues:
                    self.stdout.write(
                        self.style.WARNING(
                            'Run with --fix-issues to attempt automatic fixes'
                        )
                    )
        
        except Exception as e:
            logger.exception("Error during validation")
            raise CommandError(f'Validation failed: {str(e)}')
    
    def validate_all_data(self):
        """Validate all exhibitor data."""
        results = {
            'exhibitors': {'valid': 0, 'errors': 0, 'issues': []},
            'settings': {'valid': 0, 'errors': 0, 'issues': []},
            'leads': {'valid': 0, 'errors': 0, 'issues': []},
            'tags': {'valid': 0, 'errors': 0, 'issues': []},
            'items': {'valid': 0, 'errors': 0, 'issues': []},
            'total_errors': 0
        }
        
        # Validate exhibitors
        self.validate_exhibitors(results)
        
        # Validate settings
        self.validate_settings(results)
        
        # Validate leads
        self.validate_leads(results)
        
        # Validate tags
        self.validate_tags(results)
        
        # Validate item assignments
        self.validate_items(results)
        
        # Calculate total errors
        results['total_errors'] = sum(
            category['errors'] for category in results.values() 
            if isinstance(category, dict) and 'errors' in category
        )
        
        return results
    
    def validate_exhibitors(self, results):
        """Validate exhibitor records."""
        self.stdout.write('Validating exhibitors...')
        
        queryset = ExhibitorInfo.objects.all()
        if self.event_slug:
            queryset = queryset.filter(event__slug=self.event_slug)
        
        for exhibitor in queryset:
            try:
                # Run model validation
                exhibitor.clean()
                
                # Check required fields
                if not exhibitor.name or len(exhibitor.name.strip()) < 2:
                    self.add_issue(
                        results, 'exhibitors',
                        f'Exhibitor {exhibitor.id}: Name too short or empty'
                    )
                
                if not exhibitor.booth_name:
                    self.add_issue(
                        results, 'exhibitors',
                        f'Exhibitor {exhibitor.id}: Missing booth name'
                    )
                
                if not exhibitor.key or len(exhibitor.key) != 8:
                    self.add_issue(
                        results, 'exhibitors',
                        f'Exhibitor {exhibitor.id}: Invalid access key'
                    )
                
                # Check booth_id uniqueness
                if exhibitor.booth_id:
                    duplicates = ExhibitorInfo.objects.filter(
                        booth_id=exhibitor.booth_id
                    ).exclude(id=exhibitor.id)
                    
                    if duplicates.exists():
                        self.add_issue(
                            results, 'exhibitors',
                            f'Exhibitor {exhibitor.id}: Duplicate booth_id {exhibitor.booth_id}'
                        )
                
                results['exhibitors']['valid'] += 1
                
            except ValidationError as e:
                self.add_issue(
                    results, 'exhibitors',
                    f'Exhibitor {exhibitor.id}: {str(e)}'
                )
            except Exception as e:
                self.add_issue(
                    results, 'exhibitors',
                    f'Exhibitor {exhibitor.id}: Unexpected error - {str(e)}'
                )
    
    def validate_settings(self, results):
        """Validate exhibitor settings."""
        self.stdout.write('Validating settings...')
        
        queryset = ExhibitorSettings.objects.all()
        if self.event_slug:
            queryset = queryset.filter(event__slug=self.event_slug)
        
        for settings in queryset:
            try:
                # Check required fields
                if not settings.event:
                    self.add_issue(
                        results, 'settings',
                        f'Settings {settings.id}: Missing event reference'
                    )
                
                # Validate retention days
                if settings.lead_retention_days < 1 or settings.lead_retention_days > 3650:
                    self.add_issue(
                        results, 'settings',
                        f'Settings {settings.id}: Invalid retention days {settings.lead_retention_days}'
                    )
                
                # Validate allowed fields
                if not isinstance(settings.allowed_fields, list):
                    self.add_issue(
                        results, 'settings',
                        f'Settings {settings.id}: allowed_fields must be a list'
                    )
                
                results['settings']['valid'] += 1
                
            except Exception as e:
                self.add_issue(
                    results, 'settings',
                    f'Settings {settings.id}: {str(e)}'
                )
    
    def validate_leads(self, results):
        """Validate lead records."""
        self.stdout.write('Validating leads...')
        
        queryset = Lead.objects.select_related('exhibitor')
        if self.event_slug:
            queryset = queryset.filter(exhibitor__event__slug=self.event_slug)
        
        for lead in queryset:
            try:
                # Check required fields
                if not lead.exhibitor:
                    self.add_issue(
                        results, 'leads',
                        f'Lead {lead.id}: Missing exhibitor reference'
                    )
                
                if not lead.pseudonymization_id:
                    self.add_issue(
                        results, 'leads',
                        f'Lead {lead.id}: Missing pseudonymization_id'
                    )
                
                if not lead.scanned:
                    self.add_issue(
                        results, 'leads',
                        f'Lead {lead.id}: Missing scan timestamp'
                    )
                
                # Validate follow-up status
                valid_statuses = ['pending', 'contacted', 'qualified', 'converted']
                if lead.follow_up_status not in valid_statuses:
                    self.add_issue(
                        results, 'leads',
                        f'Lead {lead.id}: Invalid follow-up status {lead.follow_up_status}'
                    )
                
                # Check attendee data structure
                if lead.attendee and not isinstance(lead.attendee, dict):
                    self.add_issue(
                        results, 'leads',
                        f'Lead {lead.id}: attendee data must be a dictionary'
                    )
                
                results['leads']['valid'] += 1
                
            except Exception as e:
                self.add_issue(
                    results, 'leads',
                    f'Lead {lead.id}: {str(e)}'
                )
    
    def validate_tags(self, results):
        """Validate exhibitor tags."""
        self.stdout.write('Validating tags...')
        
        queryset = ExhibitorTag.objects.select_related('exhibitor')
        if self.event_slug:
            queryset = queryset.filter(exhibitor__event__slug=self.event_slug)
        
        for tag in queryset:
            try:
                # Check required fields
                if not tag.exhibitor:
                    self.add_issue(
                        results, 'tags',
                        f'Tag {tag.id}: Missing exhibitor reference'
                    )
                
                if not tag.name or len(tag.name.strip()) == 0:
                    self.add_issue(
                        results, 'tags',
                        f'Tag {tag.id}: Empty tag name'
                    )
                
                if tag.use_count < 0:
                    self.add_issue(
                        results, 'tags',
                        f'Tag {tag.id}: Negative use count {tag.use_count}'
                    )
                
                results['tags']['valid'] += 1
                
            except Exception as e:
                self.add_issue(
                    results, 'tags',
                    f'Tag {tag.id}: {str(e)}'
                )
    
    def validate_items(self, results):
        """Validate exhibitor item assignments."""
        self.stdout.write('Validating item assignments...')
        
        queryset = ExhibitorItem.objects.select_related('exhibitor')
        if self.event_slug:
            queryset = queryset.filter(exhibitor__event__slug=self.event_slug)
        
        for item_assignment in queryset:
            try:
                # Check that either exhibitor or item is present
                if not item_assignment.exhibitor and not item_assignment.item:
                    self.add_issue(
                        results, 'items',
                        f'Item assignment {item_assignment.id}: Missing both exhibitor and item references'
                    )
                
                results['items']['valid'] += 1
                
            except Exception as e:
                self.add_issue(
                    results, 'items',
                    f'Item assignment {item_assignment.id}: {str(e)}'
                )
    
    def add_issue(self, results, category, message):
        """Add a validation issue to results."""
        results[category]['errors'] += 1
        results[category]['issues'].append(message)
        
        if self.verbose:
            self.stdout.write(
                self.style.ERROR(f'  ✗ {message}')
            )
    
    def display_results(self, results):
        """Display validation results."""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('VALIDATION RESULTS')
        self.stdout.write('='*60)
        
        for category, data in results.items():
            if category == 'total_errors':
                continue
            
            self.stdout.write(f'\n{category.upper()}:')
            self.stdout.write(f'  Valid: {data["valid"]}')
            
            if data['errors'] > 0:
                self.stdout.write(
                    self.style.ERROR(f'  Errors: {data["errors"]}')
                )
                
                if not self.verbose and data['issues']:
                    self.stdout.write('  Issues:')
                    for issue in data['issues'][:5]:  # Show first 5 issues
                        self.stdout.write(f'    - {issue}')
                    
                    if len(data['issues']) > 5:
                        self.stdout.write(f'    ... and {len(data["issues"]) - 5} more')
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'  Errors: {data["errors"]}')
                )
        
        self.stdout.write(f'\nTOTAL ERRORS: {results["total_errors"]}')
        self.stdout.write('='*60)