import hashlib
import json

from asgiref.sync import async_to_sync
from django.core.files.base import ContentFile
from django.utils.timezone import now

from venueless.celery_app import app
from venueless.core.services.world import notify_world_change
from venueless.core.tasks import WorldTask
from venueless.importers.conftool import fetch_schedule_from_conftool
from venueless.storage.models import StoredFile


@app.task(base=WorldTask)
def conftool_update_schedule(world):
    u = world.config.get("conftool_url")
    p = world.config.get("conftool_password")

    if not u or not p or not world.config.get("pretalx").get("conftool"):
        return "invalid"

    d = fetch_schedule_from_conftool(u, p)
    v = d.pop("version")
    checksum = hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()
    d["version"] = v
    document = json.dumps(d, sort_keys=True)

    if StoredFile.objects.filter(
        world=world, filename=f"conftool_schedule_{checksum}.json"
    ).exists():
        return "unchanged"

    sf = StoredFile.objects.create(
        world=world,
        date=now(),
        filename=f"conftool_schedule_{checksum}.json",
        type="application/json",
        file=ContentFile(document, "schedule.json"),
        public=True,
    )
    world.config["pretalx"]["url"] = sf.file.url
    world.config["pretalx"]["conftool"] = True
    world.save()
    async_to_sync(notify_world_change)(world.id)
    return sf.pk
