# Generated by Django 4.2.11 on 2024-05-08 01:59

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('pretixapi', '0001_initial'),
        ('pretixbase', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='webhook',
            name='limit_events',
            field=models.ManyToManyField(to='pretixbase.event'),
        ),
        migrations.AddField(
            model_name='webhook',
            name='organizer',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='webhooks',
                to='pretixbase.organizer',
            ),
        ),
        migrations.AddField(
            model_name='oauthrefreshtoken',
            name='access_token',
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='refresh_token',
                to=settings.OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='oauthrefreshtoken',
            name='application',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.OAUTH2_PROVIDER_APPLICATION_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='oauthrefreshtoken',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='%(app_label)s_%(class)s',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='oauthidtoken',
            name='application',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.OAUTH2_PROVIDER_APPLICATION_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='oauthidtoken',
            name='organizers',
            field=models.ManyToManyField(to='pretixbase.organizer'),
        ),
        migrations.AddField(
            model_name='oauthidtoken',
            name='user',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='%(app_label)s_%(class)s',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='oauthgrant',
            name='application',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.OAUTH2_PROVIDER_APPLICATION_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='oauthgrant',
            name='organizers',
            field=models.ManyToManyField(to='pretixbase.organizer'),
        ),
        migrations.AddField(
            model_name='oauthgrant',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='%(app_label)s_%(class)s',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='oauthapplication',
            name='user',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='%(app_label)s_%(class)s',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='oauthaccesstoken',
            name='application',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.OAUTH2_PROVIDER_APPLICATION_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='oauthaccesstoken',
            name='id_token',
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='access_token',
                to=settings.OAUTH2_PROVIDER_ID_TOKEN_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='oauthaccesstoken',
            name='organizers',
            field=models.ManyToManyField(to='pretixbase.organizer'),
        ),
        migrations.AddField(
            model_name='oauthaccesstoken',
            name='source_refresh_token',
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='refreshed_access_token',
                to=settings.OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='oauthaccesstoken',
            name='user',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='%(app_label)s_%(class)s',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterUniqueTogether(
            name='apicall',
            unique_together={('idempotency_key', 'auth_hash')},
        ),
        migrations.AlterUniqueTogether(
            name='oauthrefreshtoken',
            unique_together={('token', 'revoked')},
        ),
    ]
