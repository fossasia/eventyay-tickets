from django.db import migrations


def initialize_billing_schedules(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    CrontabSchedule = apps.get_model('django_celery_beat', 'CrontabSchedule')

    FIRST_DAY_OF_MONTH = '1'
    MIDNIGHT_HOUR = '0'

    schedules = {
        'monthly_billing': CrontabSchedule.objects.create(
            hour='09',
            minute='43'
        ),
        'invoice_notification': CrontabSchedule.objects.create(
            hour='09',
            minute='45'
        ),
        'auto_billing': CrontabSchedule.objects.create(
            hour='09',
            minute='47'
        ),
        'retry_payment': CrontabSchedule.objects.create(
            hour='09',
            minute='49'
        ),
        'billing_status': CrontabSchedule.objects.create(
            hour='09',
            minute='52'
        )
    }

    billing_tasks = [
        {
            'name': 'monthly_billing_collection',
            'task': 'pretix.eventyay_common.tasks.monthly_billing_collect',
            'schedule': schedules['monthly_billing']
        },
        {
            'name': 'billing_invoice_notification',
            'task': 'pretix.eventyay_common.tasks.billing_invoice_notification',
            'schedule': schedules['invoice_notification']
        },
        {
            'name': 'process_auto_billing',
            'task': 'pretix.eventyay_common.tasks.process_auto_billing_charge',
            'schedule': schedules['auto_billing']
        },
        {
            'name': 'retry_failed_payment',
            'task': 'pretix.eventyay_common.tasks.retry_failed_payment',
            'schedule': schedules['retry_payment']
        },
        {
            'name': 'check_billing_status_warning',
            'task': 'pretix.eventyay_common.tasks.check_billing_status_for_warning',
            'schedule': schedules['billing_status']
        }
    ]

    for task in billing_tasks:
        if not PeriodicTask.objects.filter(name=task['name']).exists():
            PeriodicTask.objects.create(
                name=task['name'],
                task=task['task'],
                crontab=task['schedule']
            )


def reverse_billing_schedules(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    CrontabSchedule = apps.get_model('django_celery_beat', 'CrontabSchedule')

    periodic_tasks = PeriodicTask.objects.filter(
        name__in=[
            'monthly_billing_collection',
            'billing_invoice_notification',
            'process_auto_billing',
            'retry_failed_payment',
            'check_billing_status_warning'
        ]
    )

    crontab_ids = list(periodic_tasks.values_list('crontab_id', flat=True))

    periodic_tasks.delete()

    CrontabSchedule.objects.filter(id__in=crontab_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('django_celery_beat', '0019_alter_periodictasks_options'),
    ]

    operations = [
        migrations.RunPython(
            initialize_billing_schedules,
            reverse_billing_schedules
        ),
    ]
