from django.db import migrations
from django.db.models import Q

from pretalx.person.models.auth_token import READ_PERMISSIONS


def get_events_with_any_permission(Event, user):
    if user.is_administrator:
        return Event.objects.all()

    return Event.objects.filter(
        Q(
            organiser_id__in=user.teams.filter(all_events=True).values_list(
                "organiser", flat=True
            )
        )
        | Q(id__in=user.teams.values_list("limit_events__id", flat=True))
    )


def migrate_drf_tokens_to_userapitokens(apps, schema_editor):
    OldToken = apps.get_model("authtoken", "Token")
    Event = apps.get_model("event", "Event")
    User = apps.get_model("person", "User")
    UserApiToken = apps.get_model("person", "UserApiToken")

    # Not included: new endpoints, like tracks, teams, submission types, mail templates,
    # access codes, file uploads, speaker information, question options
    legacy_endpoints = [
        "events",
        "submissions",
        "speakers",
        "reviews",
        "rooms",
        "tags",
        "questions",
        "answers",
        "schedules",
        "slots",
    ]
    legacy_permissions = list(READ_PERMISSIONS)
    endpoints_data = {endpoint: legacy_permissions for endpoint in legacy_endpoints}
    token_name = "Migrated legacy API token"

    # We only migrate users with any teams
    delete_tokens = []
    new_tokens = []
    token_events = []
    existing_tokens = set(UserApiToken.objects.all().values_list("token", flat=True))
    for user in (
        User.objects.filter(teams__isnull=False, auth_token__isnull=False)
        .distinct()
        .select_related("auth_token")
    ):
        old_token = user.auth_token
        permitted_events = get_events_with_any_permission(Event, user)
        if not permitted_events or old_token in existing_tokens:
            continue
        try:
            new_tokens.append(
                UserApiToken(
                    name=token_name,
                    token=old_token.key,
                    user=user,
                    version="LEGACY",
                    endpoints=endpoints_data,
                )
            )
            token_events.append(permitted_events)
            delete_tokens.append(old_token.pk)
        except Exception as e:
            print(f"Failed to migrate auth token for user {user.email}: {e}")
    tokens = UserApiToken.objects.bulk_create(new_tokens)
    for token, events in zip(tokens, token_events):
        token.events.set(events)
    OldToken.objects.filter(pk__in=delete_tokens).delete()


def migrate_drf_tokens_to_userapitokens_reverse(apps, schema_editor):
    OldToken = apps.get_model("authtoken", "Token")
    UserApiToken = apps.get_model("person", "UserApiToken")
    for token in UserApiToken.objects.filter(version="LEGACY"):
        OldToken.objects.get_or_create(key=token.token, user=token.user)
    UserApiToken.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("person", "0033_z1_userapitoken"),
        ("authtoken", "0004_alter_tokenproxy_options"),
    ]

    operations = [
        migrations.RunPython(
            migrate_drf_tokens_to_userapitokens,
            reverse_code=migrate_drf_tokens_to_userapitokens_reverse,
        ),
    ]
