from django.db import migrations, models


def generate_booth_id():
    from django.db.models import Max

    from exhibitors.models import ExhibitorInfo
    max_id = ExhibitorInfo.objects.all().aggregate(Max('booth_id'))['booth_id__max']
    return 1000 if max_id is None else max_id + 1

class Migration(migrations.Migration):
    dependencies = [
        ('exhibitors', '0007_populate_booth_ids'),  # Reference the previous migration
    ]

    operations = [
        migrations.AlterField(
            model_name='exhibitorinfo',
            name='booth_id',
            field=models.IntegerField(default=generate_booth_id, unique=True, editable=False),
        ),
    ]
