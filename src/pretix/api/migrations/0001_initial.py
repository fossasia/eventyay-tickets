# Generated by Django 4.2.11 on 2024-05-08 01:59

import uuid

import django.db.models.deletion
import oauth2_provider.generators
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ApiCall',
            fields=[
                (
                    'id',
                    models.AutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ('idempotency_key', models.CharField(db_index=True, max_length=190)),
                ('auth_hash', models.CharField(db_index=True, max_length=190)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('locked', models.DateTimeField(null=True)),
                ('request_method', models.CharField(max_length=20)),
                ('request_path', models.CharField(max_length=255)),
                ('response_code', models.PositiveIntegerField()),
                ('response_headers', models.TextField()),
                ('response_body', models.BinaryField()),
            ],
        ),
        migrations.CreateModel(
            name='OAuthAccessToken',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('token', models.CharField(max_length=255, unique=True)),
                ('expires', models.DateTimeField()),
                ('scope', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='OAuthApplication',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('client_type', models.CharField(max_length=32)),
                ('authorization_grant_type', models.CharField(max_length=32)),
                ('skip_authorization', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('algorithm', models.CharField(default='', max_length=5)),
                ('name', models.CharField(max_length=255)),
                ('redirect_uris', models.TextField()),
                (
                    'client_id',
                    models.CharField(
                        db_index=True,
                        default=oauth2_provider.generators.generate_client_id,
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    'client_secret',
                    models.CharField(
                        db_index=True,
                        default=oauth2_provider.generators.generate_client_secret,
                        max_length=255,
                    ),
                ),
                ('active', models.BooleanField(default=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='OAuthGrant',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=255, unique=True)),
                ('expires', models.DateTimeField()),
                ('scope', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('code_challenge', models.CharField(default='', max_length=128)),
                ('code_challenge_method', models.CharField(default='', max_length=10)),
                ('nonce', models.CharField(default='', max_length=255)),
                ('claims', models.TextField()),
                ('redirect_uri', models.CharField(max_length=2500)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='OAuthIDToken',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('jti', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('expires', models.DateTimeField()),
                ('scope', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='OAuthRefreshToken',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('token', models.CharField(max_length=255)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('revoked', models.DateTimeField(null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='WebHook',
            fields=[
                (
                    'id',
                    models.AutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ('enabled', models.BooleanField(default=True)),
                ('target_url', models.URLField()),
                ('all_events', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ('id',),
            },
        ),
        migrations.CreateModel(
            name='WebHookEventListener',
            fields=[
                (
                    'id',
                    models.AutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ('action_type', models.CharField(max_length=255)),
                (
                    'webhook',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='listeners',
                        to='pretixapi.webhook',
                    ),
                ),
            ],
            options={
                'ordering': ('action_type',),
            },
        ),
        migrations.CreateModel(
            name='WebHookCall',
            fields=[
                (
                    'id',
                    models.AutoField(auto_created=True, primary_key=True, serialize=False),
                ),
                ('datetime', models.DateTimeField(auto_now_add=True)),
                ('target_url', models.URLField()),
                ('action_type', models.CharField(max_length=255)),
                ('is_retry', models.BooleanField(default=False)),
                ('execution_time', models.FloatField(null=True)),
                ('return_code', models.PositiveIntegerField(default=0)),
                ('success', models.BooleanField(default=False)),
                ('payload', models.TextField()),
                ('response_body', models.TextField()),
                (
                    'webhook',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='calls',
                        to='pretixapi.webhook',
                    ),
                ),
            ],
            options={
                'ordering': ('-datetime',),
            },
        ),
    ]
