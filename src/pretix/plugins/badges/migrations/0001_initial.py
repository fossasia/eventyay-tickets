# Generated by Django 4.2.11 on 2024-05-08 01:59

from django.db import migrations, models

import pretix.base.models.base
import pretix.plugins.badges.models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='BadgeItem',
            fields=[
                (
                    'id',
                    models.AutoField(auto_created=True, primary_key=True, serialize=False),
                ),
            ],
            options={
                'ordering': ('id',),
            },
        ),
        migrations.CreateModel(
            name='BadgeLayout',
            fields=[
                (
                    'id',
                    models.AutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ('default', models.BooleanField(default=False)),
                ('name', models.CharField(max_length=190)),
                (
                    'layout',
                    models.TextField(
                        default='[{"type":"textarea","left":"13.09","bottom":"49.73","fontsize":"23.6","color":[0,0,0,1],"fontfamily":"Open Sans","bold":true,"italic":false,"width":"121.83","content":"attendee_name","text":"Max Mustermann","align":"center"}]'
                    ),
                ),
                (
                    'background',
                    models.FileField(
                        max_length=255,
                        null=True,
                        upload_to=pretix.plugins.badges.models.bg_name,
                    ),
                ),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model, pretix.base.models.base.LoggingMixin),
        ),
    ]
