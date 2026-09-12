from django.db import migrations


def backfill_existing_event_announcements(apps, schema_editor):
    """
    Preserve backward compatibility for existing events that were configured
    for video/live features prior to experimental defaults change.

    Only events with strong signals of live/video usage are migrated:
    1. Video authentication configured (non-empty JWT_secrets)
    2. Non-empty live_features configuration
    3. Existing Announcement records in the database

    Standard ticketing events (including those with config=None, config={},
    or unconfigured live_features: {}) remain untouched.
    """
    Event = apps.get_model('base', 'Event')
    Announcement = apps.get_model('base', 'Announcement')

    event_ids_with_announcements = set(
        Announcement.objects.values_list('event_id', flat=True).distinct()
    )

    for event in Event.objects.all():
        config = event.config
        has_config_dict = isinstance(config, dict)
        has_jwt_secrets = has_config_dict and bool(config.get('JWT_secrets'))
        has_active_live_features = (
            has_config_dict
            and isinstance(config.get('live_features'), dict)
            and bool(config['live_features'])
        )
        has_announcements = event.id in event_ids_with_announcements

        if not (has_jwt_secrets or has_active_live_features or has_announcements):
            continue

        if not has_config_dict:
            config = {}

        live_features = config.get('live_features')
        if live_features is None:
            config['live_features'] = {'announcements': True}
            event.config = config
            event.save(update_fields=['config'])
        elif isinstance(live_features, dict) and 'announcements' not in live_features:
            live_features['announcements'] = True
            config['live_features'] = live_features
            event.config = config
            event.save(update_fields=['config'])


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0070_alter_voucher_budget_alter_voucher_value'),
    ]

    operations = [
        migrations.RunPython(
            backfill_existing_event_announcements,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
