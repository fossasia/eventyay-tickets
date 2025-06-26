from django.db import migrations, models
import i18nfield.fields


class Migration(migrations.Migration):
    dependencies = [
        ("submission", "0046_question_submission_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="track",
            name="description",
            field=i18nfield.fields.I18nTextField(blank=True),
        ),
    ]
