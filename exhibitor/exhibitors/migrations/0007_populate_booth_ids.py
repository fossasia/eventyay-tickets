from django.db import migrations


def populate_booth_ids(apps, schema_editor):
    ExhibitorInfo = apps.get_model('exhibitors', 'ExhibitorInfo')
    starting_id = 1000
    
    # Update all exhibitors that don't have a booth_id
    for exhibitor in ExhibitorInfo.objects.all().order_by('id'):
        exhibitor.booth_id = starting_id
        exhibitor.save()
        starting_id += 1

def reverse_populate_booth_ids(apps, schema_editor):
    ExhibitorInfo = apps.get_model('exhibitors', 'ExhibitorInfo')
    ExhibitorInfo.objects.all().update(booth_id=None)

class Migration(migrations.Migration):
    dependencies = [
        ('exhibitors', '0006_exhibitorinfo_allow_lead_access_and_more'),  # Note: removed .py
    ]

    operations = [
        migrations.RunPython(populate_booth_ids, reverse_populate_booth_ids),
    ]
