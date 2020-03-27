import hashlib
import logging

import django_libsass
import sass
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.templatetags.static import static

from pretalx.celery_app import app
from pretalx.event.models import Event

logger = logging.getLogger(__name__)


def generate_widget_css(event, save=True):
    agenda_path = finders.find("agenda/scss/_agenda.scss")
    variables_path = finders.find("common/scss/_variables.scss")
    custom_functions = dict(django_libsass.CUSTOM_FUNCTIONS)
    custom_functions["static"] = static
    sassrules = []
    if event.primary_color:
        sassrules.append(f"$brand-primary: {event.primary_color};")
        sassrules.append("$link-color: $brand-primary;")
    sassrules.append(f'@import "{variables_path}";')
    sassrules.append(f'@import "{agenda_path}";')
    css = sass.compile(
        string="\n".join(sassrules),
        output_style="compressed",
        custom_functions=custom_functions,
    ).encode("utf-8")
    if save:
        checksum = hashlib.sha1(css).hexdigest()
        if event.settings.widget_css_checksum != checksum:
            file_name = default_storage.save(
                f"widget/widget.{checksum}.css", ContentFile(css)
            )
            event.settings.set("widget_css", "file://" + file_name)
            event.settings.set("widget_css_checksum", checksum)
    return css


def generate_widget_js(event, locale, save=True):
    code = f"""
const lang = "{locale}";
let dataSource = "{event.urls.widget_data_source}";
"""
    files = [
        "vendored/vue.js" if settings.DEBUG else "vendored/vue.min.js",
        "vendored/moment-with-locales.js",
        "agenda/js/widget.js",
    ]
    for fname in files:
        f = finders.find(fname)
        with open(f, "r", encoding="utf-8") as fp:
            code += fp.read()
    data = code.encode()
    if save:
        checksum = hashlib.sha1(data).hexdigest()
        if checksum != event.settings.get(f"widget_checksum_{locale}"):
            file_name = default_storage.save(
                f"widget/widget.{locale}.{checksum}.js", ContentFile(data)
            )
            event.settings.set(f"widget_file_{locale}", "file://" + file_name)
            event.settings.set(f"widget_checksum_{locale}", checksum)
    return data


@app.task()
def regenerate_css(event_id: int):
    event = Event.objects.filter(pk=event_id).first()
    local_apps = ["agenda", "cfp"]
    if not event:
        logger.error(f"In regenerate_css: Event ID {event_id} not found.")
        return

    if event.settings.widget_css_checksum:
        generate_widget_css(event)
    for locale in event.locales:
        if event.settings.get(f"widget_checksum_{locale}"):
            generate_widget_js(event, locale)

    if not event.primary_color:
        for local_app in local_apps:
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
            newname = default_storage.save(fname, ContentFile(css))
            event.settings.set(f"{local_app}_css_file", f"{settings.MEDIA_URL}{newname}")
            event.settings.set(f"{local_app}_css_checksum", checksum)
