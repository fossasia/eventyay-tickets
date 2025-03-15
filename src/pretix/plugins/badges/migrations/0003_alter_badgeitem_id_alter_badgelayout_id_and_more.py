# Generated by Django 4.2.16 on 2024-10-08 04:57

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('badges', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='badgelayout',
            name='size',
            field=models.TextField(
                default='[{"width": 148, "height": 105, "orientation": "portrait"}]'
            ),
        ),
        migrations.AlterField(
            model_name='badgeitem',
            name='id',
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name='badgelayout',
            name='id',
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name='badgelayout',
            name='size',
            field=models.TextField(
                default='[{"width": 148, "height": 105, "orientation": "landscape"}]'
            ),
        ),
    ]
