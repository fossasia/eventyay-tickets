# Generated by Django 4.2.13 on 2024-06-25 06:46

import i18nfield.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('pretixbase', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='description',
            field=i18nfield.fields.I18nTextField(default='', null=True),
        ),
    ]
