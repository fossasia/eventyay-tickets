from django.db import migrations


def migrate_data(apps, schema_editor):
    Event = apps.get_model("event", "Event")
    EventSettings = apps.get_model("event", "Event_SettingsStore")
    VenuelessSettings = apps.get_model("pretalx_venueless", "VenuelessSettings")
    for event in Event.objects.all().filter(plugins__contains="pretalx_venueless"):
        url = EventSettings.objects.filter(object=event, key="venueless_url").first()
        token = EventSettings.objects.filter(
            object=event, key="venueless_token"
        ).first()
        return_url = EventSettings.objects.filter(
            object=event, key="return_url"
        ).first()
        last_push = EventSettings.objects.filter(
            object=event, key="venueless_last_push"
        ).first()
        VenuelessSettings.objects.create(
            event=event,
            url=url.value if url else None,
            token=token.value if token else None,
            return_url=return_url.value if return_url else None,
            last_push=last_push.value if last_push else None,
        )


def delete_all_settings(apps, schema_editor):
    VenuelessSettings = apps.get_model("pretalx_venueless", "VenuelessSettings")
    VenuelessSettings.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("pretalx_venueless", "0001_initial"),
    ]

    operations = [migrations.RunPython(migrate_data, delete_all_settings)]
