# Generated by Django 5.1.3 on 2024-11-22 08:34

import i18nfield.fields
from django.db import migrations, models

import pretix.base.models.base


class Migration(migrations.Migration):

    dependencies = [
        ("pretixbase", "0004_create_billing_invoice"),
    ]

    operations = [
        migrations.CreateModel(
            name="Page",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("title", i18nfield.fields.I18nCharField()),
                ("slug", models.CharField(db_index=True, max_length=150)),
                ("link_on_website_start_page", models.BooleanField(default=False)),
                ("link_in_header", models.BooleanField(default=False)),
                ("link_in_footer", models.BooleanField(default=False)),
                ("require_confirmation", models.BooleanField(default=False)),
                ("text", i18nfield.fields.I18nTextField()),
            ],
            options={
                "abstract": False,
            },
            bases=(models.Model, pretix.base.models.base.LoggingMixin),
        ),
    ]
