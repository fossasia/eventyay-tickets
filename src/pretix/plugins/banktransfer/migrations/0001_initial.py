# Generated by Django 4.2.11 on 2024-05-08 01:59

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='BankImportJob',
            fields=[
                (
                    'id',
                    models.AutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('state', models.CharField(default='pending', max_length=32)),
            ],
            options={
                'ordering': ('id',),
            },
        ),
        migrations.CreateModel(
            name='BankTransaction',
            fields=[
                (
                    'id',
                    models.AutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ('state', models.CharField(default='imported', max_length=32)),
                ('message', models.TextField()),
                ('checksum', models.CharField(db_index=True, max_length=190)),
                ('payer', models.TextField()),
                ('reference', models.TextField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('date', models.CharField(max_length=50)),
                ('date_parsed', models.DateField(null=True)),
                ('iban', models.CharField(max_length=250)),
                ('bic', models.CharField(max_length=250)),
                ('comment', models.TextField()),
            ],
            options={
                'ordering': ('date', 'id'),
            },
        ),
        migrations.CreateModel(
            name='RefundExport',
            fields=[
                (
                    'id',
                    models.AutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ('datetime', models.DateTimeField(auto_now_add=True)),
                ('testmode', models.BooleanField(default=False)),
                ('rows', models.TextField(default='[]')),
                ('downloaded', models.BooleanField(default=False)),
            ],
        ),
    ]
