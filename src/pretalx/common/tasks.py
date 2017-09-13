import hashlib

import django_libsass
import sass
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.templatetags.static import static

from pretalx.celery_app import app
from pretalx.event.models import Event


@app.task()
def regenerate_css(event_id: int):
    event = Event.objects.get(pk=event_id)
    local_apps = ['cfp', 'orga']

    if not event.primary_color:
        for local_app in local_apps:
            event.settings.delete(f'{local_app}_css_file')
        return

    for local_app in local_apps:
        sassrules = []
        if event.primary_color:
            sassrules.append('$brand-primary: {};'.format(event.primary_color))

        sassrules.append(f'@import "pretalx/static/{local_app}/scss/main.scss";')

        cf = dict(django_libsass.CUSTOM_FUNCTIONS)
        cf['static'] = static
        css = sass.compile(
            string="\n".join(sassrules),
            output_style='compressed',
            custom_functions=cf
        )
        checksum = hashlib.sha1(css.encode('utf-8')).hexdigest()
        fname = f'{event.slug}/{local_app}.{checksum[:16]}.css'

        if event.settings.get(f'{local_app}_css_checksum', '') != checksum:
            newname = default_storage.save(fname, ContentFile(css.encode('utf-8')))
            event.settings.set(f'{local_app}_css_file', f'/media/{newname}')
            event.settings.set(f'{local_app}_css_checksum', checksum)
