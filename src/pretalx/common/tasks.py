import hashlib
import logging

import django_libsass
import sass
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.templatetags.static import static

from pretalx.celery_app import app
from pretalx.event.models import Event

logger = logging.getLogger(__name__)


def delete_media_file(path):
    if not path:
        return
    # path might be a File object
    if hasattr(path, "path"):
        path = path.path
    if not isinstance(path, str):
        path = str(path)
    if path.startswith("file://"):
        path = path.replace("file://", "")
    media_dir = settings.MEDIA_ROOT
    if path.startswith(media_dir.name + "/"):
        path = path[len(media_dir.name) + 1 :]
    path = media_dir / path
    if path.exists():
        default_storage.delete(str(path))


@app.task()
def regenerate_css(event_id: int):
    event = Event.objects.filter(pk=event_id).first()
    local_apps = ["agenda", "cfp"]
    if not event:
        logger.error(f"In regenerate_css: Event ID {event_id} not found.")
        return

    if not event.primary_color:
        for local_app in local_apps:
            old_path = event.settings.get(f"{local_app}_css_file", "")
            delete_media_file(old_path)
            event.settings.delete(f"{local_app}_css_file")
            event.settings.delete(f"{local_app}_css_checksum")
        return

    for local_app in local_apps:
        path = settings.STATIC_ROOT / local_app / "scss/main.scss"
        sassrules = []
        sassrules.append(f"$brand-primary: {event.primary_color};")
        sassrules.append("$link-color: $brand-primary;")
        sassrules.append(f'@import "{path}";')

        custom_functions = dict(django_libsass.CUSTOM_FUNCTIONS)
        custom_functions["static"] = static
        css = sass.compile(
            string="\n".join(sassrules),
            output_style="compressed",
            custom_functions=custom_functions,
        ).encode("utf-8")
        checksum = hashlib.sha1(css).hexdigest()
        fname = f"{event.slug}/{local_app}.{checksum[:16]}.css"

        if event.settings.get(f"{local_app}_css_checksum", "") != checksum:
            old_path = event.settings.get(f"{local_app}_css_file", "")
            delete_media_file(old_path)
            newname = default_storage.save(fname, ContentFile(css))
            event.settings.set(
                f"{local_app}_css_file", f"{settings.MEDIA_URL}{newname}"
            )
            event.settings.set(f"{local_app}_css_checksum", checksum)
