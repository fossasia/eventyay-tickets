from django.db import migrations, models


# Only the new classification fields are set here. Existing is_active,
# enable_by_default, and show_in_organizer_list values are preserved for
# rows that already exist.
PLATFORM_PLUGINS = {
    # Payment providers — configured via event payment settings
    'eventyay_stripe': {
        'plugin_type': 'payment_provider',
        'is_required': False,
        'configured_via': 'payment_settings',
    },
    'eventyay_paypal': {
        'plugin_type': 'payment_provider',
        'is_required': False,
        'configured_via': 'payment_settings',
    },
    'eventyay.plugins.banktransfer': {
        'plugin_type': 'payment_provider',
        'is_required': False,
        'configured_via': 'payment_settings',
    },
    'eventyay.plugins.manualpayment': {
        'plugin_type': 'payment_provider',
        'is_required': False,
        'configured_via': 'payment_settings',
    },
    'eventyay_bitpay': {
        'plugin_type': 'payment_provider',
        'is_required': False,
        'configured_via': 'payment_settings',
    },
    # System plugins — platform-level features.
    # Report exporter and Check-in list exporter are deeply integrated
    # system features (PDF exports, check-in infrastructure) that run
    # behind the scenes across many parts of the platform.  They are
    # hidden from the admin plugin management UI but remain fully
    # functional in the system.
    # SocialAuth provides social login.  It is kept modular so that
    # deployments not using social authentication can disable it without
    # breaking anything — the platform falls back to local auth.
    'eventyay.plugins.reports': {
        'plugin_type': 'system',
        'is_required': False,
        'configured_via': 'platform',
    },
    'eventyay.plugins.socialauth': {
        'plugin_type': 'system',
        'is_required': False,
        'configured_via': 'platform',
    },
    'eventyay.plugins.checkinlists': {
        'plugin_type': 'system',
        'is_required': True,
        'configured_via': 'platform',
    },
}


def populate_plugin_classification(apps, schema_editor):
    GlobalPluginConfig = apps.get_model('base', 'GlobalPluginConfig')

    for module, fields in PLATFORM_PLUGINS.items():
        obj, created = GlobalPluginConfig.objects.get_or_create(
            module=module,
            defaults={
                'is_active': True,
                'enable_by_default': False,
                'show_in_organizer_list': False,
                **fields,
            },
        )
        if not created:
            for attr, value in fields.items():
                setattr(obj, attr, value)
            # Required plugins must be active — repair if previously disabled.
            if fields.get('is_required') and not obj.is_active:
                obj.is_active = True
            obj.save(update_fields=[*fields.keys(), 'is_active'])

    GlobalPluginConfig.objects.exclude(
        module__in=PLATFORM_PLUGINS.keys()
    ).filter(plugin_type='').update(plugin_type='external')


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0070_alter_voucher_budget_alter_voucher_value'),
    ]

    operations = [
        migrations.AddField(
            model_name='globalpluginconfig',
            name='plugin_type',
            field=models.CharField(
                choices=[
                    ('payment_provider', 'Payment provider'),
                    ('system', 'System plugin'),
                    ('external', 'External plugin'),
                ],
                default='external',
                help_text='Classification of the plugin.',
                max_length=32,
                verbose_name='Plugin type',
            ),
        ),
        migrations.AddField(
            model_name='globalpluginconfig',
            name='is_required',
            field=models.BooleanField(
                default=False,
                help_text='Required plugins cannot be deactivated.',
                verbose_name='Required',
            ),
        ),
        migrations.AddField(
            model_name='globalpluginconfig',
            name='configured_via',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Describes where this plugin is configured (e.g. payment_settings, platform).',
                max_length=64,
                verbose_name='Configured via',
            ),
        ),
        migrations.RunPython(
            populate_plugin_classification,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
