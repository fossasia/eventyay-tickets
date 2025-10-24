from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0004_streamingserver_event_config_event_domain_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_wikimedia_user',
            field=models.BooleanField(default=False, verbose_name='Is Wikimedia user'),
        ),
    ]
