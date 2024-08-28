import datetime as dt
import sys
import uuid

import requests
from django.conf import settings
from django.dispatch import receiver
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext_noop
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString

from pretalx import __version__ as pretalx_version
from pretalx.celery_app import app
from pretalx.common.mail import mail_send_task
from pretalx.common.models.settings import GlobalSettings
from pretalx.common.plugins import get_all_plugins
from pretalx.common.signals import minimum_interval, periodic_task
from pretalx.event.models import Event


@receiver(signal=periodic_task)
@minimum_interval(minutes_after_success=60 * 23)
def run_update_check(sender, **kwargs):
    gs = GlobalSettings()
    if not gs.settings.update_check_enabled:
        return

    if (
        not gs.settings.update_check_last
        or now() - gs.settings.update_check_last > dt.timedelta(hours=23)
    ):
        update_check.apply_async()


@app.task(name="pretalx.common.update_check")
@scopes_disabled()
def update_check():
    gs = GlobalSettings()

    if not gs.settings.update_check_enabled:
        return

    if not gs.settings.update_check_id:
        gs.settings.set("update_check_id", uuid.uuid4().hex)

    if "runserver" in sys.argv:  # pragma: no cover
        gs.settings.set("update_check_last", now())
        gs.settings.set("update_check_result", {"error": "development"})
        return

    check_payload = {
        "id": gs.settings.update_check_id,
        "version": pretalx_version,
        "events": {
            "total": Event.objects.count(),
            "public": Event.objects.filter(is_public=True).count(),
        },
        "plugins": [
            {"name": plugin.module, "version": plugin.version}
            for plugin in get_all_plugins()
        ],
    }
    try:
        response = requests.post(
            "https://pretalx.com/.update_check/",
            json=check_payload,
            timeout=30,
        )
    except requests.RequestException:  # pragma: no cover
        gs.settings.set("update_check_last", now())
        gs.settings.set("update_check_result", {"error": "unavailable"})
        return

    gs.settings.set("update_check_last", now())
    if response.status_code != 200:
        gs.settings.set("update_check_result", {"error": "http_error"})
        return

    rdata = response.json()
    update_available = rdata["version"]["updatable"] or any(
        plugin["updatable"] for plugin in rdata["plugins"].values()
    )
    gs.settings.set("update_check_result_warning", update_available)
    if update_available and rdata != gs.settings.update_check_result:
        send_update_notification_email()
    gs.settings.set("update_check_result", rdata)


def send_update_notification_email():
    gs = GlobalSettings()
    if not gs.settings.update_check_email:
        return

    mail_send_task.apply_async(
        kwargs={
            "to": [gs.settings.update_check_email],
            "subject": _("pretalx update available"),
            "body": str(
                LazyI18nString.from_gettext(
                    gettext_noop(
                        "Hi!\n\nAn update is available for pretalx or for one of the plugins you installed in your "
                        "pretalx installation at {base_url}.\nPlease follow this link for more information:\n\n {url} \n\n"
                        "You can always find information on the latest updates in the changelog:\n\n"
                        "  https://docs.pretalx.org/changelog.html\n\n"
                        "Larger updates are also announced with upgrade notes on the pretalx.com blog:\n\n"
                        "  https://pretalx.com/p/news"
                        "\n\nBest regards,\nyour pretalx developers"
                    ),
                )
            ).format(
                base_url=settings.SITE_URL,
                url=settings.SITE_URL + reverse("orga:admin.update"),
            ),
            "html": None,
        },
        ignore_result=True,
    )


def check_result_table():
    gs = GlobalSettings()
    res = gs.settings.update_check_result
    if not res:
        return {"error": "no_result"}

    if "error" in res:
        return res

    table = [
        (
            "pretalx",
            pretalx_version,
            res["version"]["latest"],
            res["version"]["updatable"],
        )
    ]
    for plugin in get_all_plugins():
        if plugin.module in res["plugins"]:
            pdata = res["plugins"][plugin.module]
            table.append(
                (
                    _("Plugin") + f": {plugin.name}",
                    plugin.version,
                    pdata["latest"],
                    pdata["updatable"],
                )
            )
        else:
            table.append((_("Plugin") + f": {plugin.name}", plugin.version, "?", False))

    return table
