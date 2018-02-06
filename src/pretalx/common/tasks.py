import hashlib
import logging
import os

import django_libsass
import sass
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.templatetags.static import static

from pretalx.celery_app import app
from pretalx.event.models import Event

logger = logging.getLogger(__name__)


@app.task()
def regenerate_css(event_id: int):
    event = Event.objects.filter(pk=event_id).first()
    if not event:
        logger.error(f'In regenerate_css: Event ID {event_id} not found.')

    local_apps = ['agenda', 'cfp', 'orga']
    if not event.primary_color:
        for local_app in local_apps:
            event.settings.delete(f'{local_app}_css_file')
            event.settings.delete(f'{local_app}_css_checksum')
        return

    for local_app in local_apps:
        path = os.path.join(settings.STATIC_ROOT, local_app, 'scss/main.scss')
        sassrules = []

        if event.primary_color:
            sassrules.append('$brand-primary: {};'.format(event.primary_color))
            sassrules.append(f'@import "{path}";')

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
