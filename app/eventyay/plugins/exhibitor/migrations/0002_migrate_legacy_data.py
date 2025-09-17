# Migration to transfer data from legacy eventyay-tickets exhibitor system

from django.db import migrations
import logging

logger = logging.getLogger(__name__)


def migrate_exhibitor_data(apps, schema_editor):
    """
    Migrate exhibitor data from legacy system.
    This is a placeholder for the actual migration logic.
    """
    # Get models
    ExhibitorInfo = apps.get_model('exhibitor', 'ExhibitorInfo')
    ExhibitorSettings = apps.get_model('exhibitor', 'ExhibitorSettings')
    Lead = apps.get_model('exhibitor', 'Lead')
    ExhibitorTag = apps.get_model('exhibitor', 'ExhibitorTag')
    ExhibitorItem = apps.get_model('exhibitor', 'ExhibitorItem')
    
    # This would contain the actual migration logic
    # For now, we'll just log that the migration ran
    logger.info("Legacy exhibitor data migration started")
    
    # Example migration logic (would be customized based on actual legacy schema):
    """
    # Migrate exhibitor info
    legacy_exhibitors = get_legacy_exhibitors()  # Custom function to get legacy data
    for legacy_exhibitor in legacy_exhibitors:
        exhibitor = ExhibitorInfo.objects.create(
            event_id=legacy_exhibitor['event_id'],
            name=legacy_exhibitor['name'],
            description=legacy_exhibitor.get('description'),
            url=legacy_exhibitor.get('url'),
            email=legacy_exhibitor.get('email'),
            logo=legacy_exhibitor.get('logo'),
            key=legacy_exhibitor['key'],
            booth_id=legacy_exhibitor.get('booth_id'),
            booth_name=legacy_exhibitor['booth_name'],
            lead_scanning_enabled=legacy_exhibitor.get('lead_scanning_enabled', False),
            allow_voucher_access=legacy_exhibitor.get('allow_voucher_access', False),
            allow_lead_access=legacy_exhibitor.get('allow_lead_access', False),
            lead_scanning_scope_by_device=legacy_exhibitor.get('lead_scanning_scope_by_device', False),
            # Map legacy fields to new enhanced fields
            is_active=True,
            sort_order=0,
            featured=False
        )
        
        # Migrate associated leads
        legacy_leads = get_legacy_leads(legacy_exhibitor['id'])
        for legacy_lead in legacy_leads:
            Lead.objects.create(
                exhibitor=exhibitor,
                exhibitor_name=legacy_lead['exhibitor_name'],
                pseudonymization_id=legacy_lead['pseudonymization_id'],
                scanned=legacy_lead['scanned'],
                scan_type=legacy_lead['scan_type'],
                device_name=legacy_lead['device_name'],
                attendee=legacy_lead.get('attendee'),
                booth_id=legacy_lead['booth_id'],
                booth_name=legacy_lead['booth_name'],
                # New fields with defaults
                notes='',
                follow_up_status='pending'
            )
        
        # Migrate tags
        legacy_tags = get_legacy_tags(legacy_exhibitor['id'])
        for legacy_tag in legacy_tags:
            ExhibitorTag.objects.create(
                exhibitor=exhibitor,
                name=legacy_tag['name'],
                use_count=legacy_tag.get('use_count', 0)
            )
        
        # Migrate item assignments
        legacy_items = get_legacy_exhibitor_items(legacy_exhibitor['id'])
        for legacy_item in legacy_items:
            if legacy_item['item_id']:
                ExhibitorItem.objects.create(
                    exhibitor=exhibitor,
                    item_id=legacy_item['item_id']
                )
    
    # Migrate settings
    legacy_settings = get_legacy_settings()
    for legacy_setting in legacy_settings:
        ExhibitorSettings.objects.create(
            event_id=legacy_setting['event_id'],
            exhibitors_access_mail_subject=legacy_setting.get('exhibitors_access_mail_subject', ''),
            exhibitors_access_mail_body=legacy_setting.get('exhibitors_access_mail_body', ''),
            allowed_fields=legacy_setting.get('allowed_fields', []),
            # New fields with defaults
            enable_public_directory=True,
            enable_lead_export=True,
            lead_retention_days=365
        )
    """
    
    logger.info("Legacy exhibitor data migration completed")


def reverse_migrate_exhibitor_data(apps, schema_editor):
    """
    Reverse migration - remove migrated data.
    """
    logger.info("Reversing exhibitor data migration")
    
    # Get models
    ExhibitorInfo = apps.get_model('exhibitor', 'ExhibitorInfo')
    ExhibitorSettings = apps.get_model('exhibitor', 'ExhibitorSettings')
    Lead = apps.get_model('exhibitor', 'Lead')
    ExhibitorTag = apps.get_model('exhibitor', 'ExhibitorTag')
    ExhibitorItem = apps.get_model('exhibitor', 'ExhibitorItem')
    
    # Delete all migrated data
    ExhibitorItem.objects.all().delete()
    ExhibitorTag.objects.all().delete()
    Lead.objects.all().delete()
    ExhibitorInfo.objects.all().delete()
    ExhibitorSettings.objects.all().delete()
    
    logger.info("Exhibitor data migration reversed")


class Migration(migrations.Migration):
    """
    Data migration for transferring exhibitor data from legacy system.
    """
    
    dependencies = [
        ('exhibitor', '0001_initial'),
    ]
    
    operations = [
        migrations.RunPython(
            migrate_exhibitor_data,
            reverse_migrate_exhibitor_data,
            hints={'target_db': 'default'}
        ),
    ]