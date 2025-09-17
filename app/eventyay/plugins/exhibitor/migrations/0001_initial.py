# Generated migration for exhibitor plugin
from django.db import migrations, models
import django.db.models.deletion
from django_scopes import ScopedManager


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('base', '0001_initial'),  # Assuming base app has initial migration
    ]

    operations = [
        # We'll create tables manually for now to avoid dependency issues
        migrations.RunSQL(
            """
            -- Create exhibitor_settings table
            CREATE TABLE IF NOT EXISTS exhibitor_exhibitorsettings (
                id SERIAL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                exhibitors_access_mail_subject VARCHAR(255) DEFAULT 'Your exhibitor access credentials',
                exhibitors_access_mail_body TEXT DEFAULT 'Please find your exhibitor access credentials below.',
                allowed_fields JSONB DEFAULT '[]',
                enable_public_directory BOOLEAN DEFAULT true,
                enable_lead_export BOOLEAN DEFAULT true,
                lead_retention_days INTEGER DEFAULT 365,
                created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            -- Create exhibitor_info table
            CREATE TABLE IF NOT EXISTS exhibitor_exhibitorinfo (
                id SERIAL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                name VARCHAR(190) NOT NULL,
                description TEXT,
                url VARCHAR(200),
                email VARCHAR(254),
                logo VARCHAR(100),
                key VARCHAR(8) NOT NULL,
                booth_id VARCHAR(100) UNIQUE,
                booth_name VARCHAR(100) NOT NULL,
                lead_scanning_enabled BOOLEAN DEFAULT false,
                allow_voucher_access BOOLEAN DEFAULT false,
                allow_lead_access BOOLEAN DEFAULT false,
                lead_scanning_scope_by_device BOOLEAN DEFAULT false,
                is_active BOOLEAN DEFAULT true,
                sort_order INTEGER DEFAULT 0,
                featured BOOLEAN DEFAULT false,
                created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            -- Create lead table
            CREATE TABLE IF NOT EXISTS exhibitor_lead (
                id SERIAL PRIMARY KEY,
                exhibitor_id INTEGER NOT NULL,
                exhibitor_name VARCHAR(190) NOT NULL,
                pseudonymization_id VARCHAR(190) NOT NULL,
                scanned TIMESTAMP WITH TIME ZONE NOT NULL,
                scan_type VARCHAR(50) NOT NULL,
                device_name VARCHAR(50) NOT NULL,
                attendee JSONB,
                booth_id VARCHAR(100) NOT NULL,
                booth_name VARCHAR(100) NOT NULL,
                notes TEXT DEFAULT '',
                follow_up_status VARCHAR(20) DEFAULT 'pending',
                follow_up_date TIMESTAMP WITH TIME ZONE,
                created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            -- Create exhibitor_tag table
            CREATE TABLE IF NOT EXISTS exhibitor_exhibitortag (
                id SERIAL PRIMARY KEY,
                exhibitor_id INTEGER NOT NULL,
                name VARCHAR(50) NOT NULL,
                color VARCHAR(7) DEFAULT '#007bff',
                usage_count INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            -- Create exhibitor_item table
            CREATE TABLE IF NOT EXISTS exhibitor_exhibitoritem (
                id SERIAL PRIMARY KEY,
                product_id INTEGER,
                exhibitor_id INTEGER,
                is_primary BOOLEAN DEFAULT false,
                created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            -- Create indexes
            CREATE INDEX IF NOT EXISTS exhibitor_exhibitorinfo_event_id ON exhibitor_exhibitorinfo(event_id);
            CREATE INDEX IF NOT EXISTS exhibitor_lead_exhibitor_id ON exhibitor_lead(exhibitor_id);
            CREATE INDEX IF NOT EXISTS exhibitor_lead_scanned ON exhibitor_lead(scanned);
            CREATE INDEX IF NOT EXISTS exhibitor_exhibitortag_exhibitor_id ON exhibitor_exhibitortag(exhibitor_id);
            """,
            reverse_sql="DROP TABLE IF EXISTS exhibitor_exhibitoritem, exhibitor_exhibitortag, exhibitor_lead, exhibitor_exhibitorinfo, exhibitor_exhibitorsettings CASCADE;"
        ),
    ]
