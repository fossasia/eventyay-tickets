# Generated by Django 5.1.2 on 2024-11-05 04:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pretixbase", "0003_create_billing_invoice_table"),
    ]

    operations = [
        migrations.AddField(
            model_name="billinginvoice",
            name="stripe_payment_intent_id",
            field=models.CharField(max_length=50, null=True),
        )
    ]