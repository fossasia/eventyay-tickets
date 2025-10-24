import sys
import uuid
from datetime import timedelta

import requests
from django.dispatch import receiver
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext_noop
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString

from eventyay import __version__
from eventyay.base.models import Event
from eventyay.base.plugins import get_all_plugins
from eventyay.base.services.mail import mail
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.signals import periodic_task
from eventyay.celery_app import app
from eventyay.helpers.urls import build_absolute_uri


@receiver(signal=periodic_task)
def run_update_check(sender, **kwargs):
    gs = GlobalSettingsObject()
    if not gs.settings.update_check_perform:
        return

    if not gs.settings.update_check_last or now() - gs.settings.update_check_last > timedelta(hours=23):
        update_check.apply_async()


@app.task
@scopes_disabled()
def update_check():
    gs = GlobalSettingsObject()

    if not gs.settings.update_check_id:
        gs.settings.set('update_check_id', uuid.uuid4().hex)

    if not gs.settings.update_check_perform:
        return

    if 'runserver' in sys.argv:
        gs.settings.set('update_check_last', now())
        gs.settings.set('update_check_result', {'error': 'development'})
        return

    check_payload = {
        'id': gs.settings.get('update_check_id'),
        'version': __version__,
        'events': {
            'total': Event.objects.count(),
            'live': Event.objects.filter(live=True).count(),
        },
        'plugins': [{'name': p.module, 'version': p.version} for p in get_all_plugins()],
    }
    try:
        r = requests.post('https://eventyay.org/.update_check/', json=check_payload)
        gs.settings.set('update_check_last', now())
        if r.status_code != 200:
            gs.settings.set('update_check_result', {'error': 'http_error'})
        else:
            rdata = r.json()
            update_available = rdata['version']['updatable'] or any(p['updatable'] for p in rdata['plugins'].values())
            gs.settings.set('update_check_result_warning', update_available)
            if update_available and rdata != gs.settings.update_check_result:
                send_update_notification_email()
            gs.settings.set('update_check_result', rdata)
    except requests.RequestException:
        gs.settings.set('update_check_last', now())
        gs.settings.set('update_check_result', {'error': 'unavailable'})


def send_update_notification_email():
    gs = GlobalSettingsObject()
    if not gs.settings.update_check_email:
        return

    mail(
        gs.settings.update_check_email,
        _('pretix update available'),
        LazyI18nString.from_gettext(
            gettext_noop(
                'Hi!\n\nAn update is available for pretix or for one of the plugins you installed in your '
                'pretix installation. Please click on the following link for more information:\n\n {url} \n\n'
                'You can always find information on the latest updates on the eventyay.com blog:\n\n'
                'https://eventyay.com/about/en/blog/'
                '\n\nBest,\n\nyour pretix developers'
            )
        ),
        {'url': build_absolute_uri('eventyay_admin:admin.global.update')},
    )


def check_result_table():
    gs = GlobalSettingsObject()
    res = gs.settings.update_check_result
    if not res:
        return {'error': 'no_result'}

    if 'error' in res:
        return res

    table = []
    table.append(('pretix', __version__, res['version']['latest'], res['version']['updatable']))
    for p in get_all_plugins():
        if p.module in res['plugins']:
            pdata = res['plugins'][p.module]
            table.append(
                (
                    _('Plugin: %s') % p.name,
                    p.version,
                    pdata['latest'],
                    pdata['updatable'],
                )
            )
        else:
            table.append((_('Plugin: %s') % p.name, p.version, '?', False))

    return table
