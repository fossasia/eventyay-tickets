# Generated by Django 4.2.11 on 2024-05-08 01:59

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Thumbnail",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("source", models.CharField(max_length=255)),
                ("size", models.CharField(max_length=255)),
                ("thumb", models.FileField(max_length=255, upload_to="pub/thumbs/")),
            ],
            options={
                "unique_together": {("source", "size")},
            },
        ),
    ]
