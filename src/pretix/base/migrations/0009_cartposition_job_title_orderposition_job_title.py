# Generated by Django 5.1.4 on 2025-03-09 08:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pretixbase', '0008_alter_cachedcombinedticket_id_alter_cachedticket_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartposition',
            name='job_title',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='orderposition',
            name='job_title',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
