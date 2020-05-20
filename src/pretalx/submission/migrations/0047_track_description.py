from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("submission", "0046_question_submission_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="track",
            name="description",
            field=models.TextField(blank=True)
        ),
    ]
