from contextlib import suppress

from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from pretalx.cfp.signals import html_above_profile_page, html_above_submission_list
from pretalx.orga.signals import nav_event_settings
from pretalx.schedule.signals import schedule_release

from .venueless import push_to_venueless


@receiver(schedule_release, dispatch_uid="venuless_schedule_release")
def on_schedule_release(sender, schedule, user, **kwargs):
    try:
        venueless_settings = sender.venueless_settings
    except Exception:
        return
    if not (venueless_settings.url and venueless_settings.token):
        return
    with suppress(Exception):
        push_to_venueless(sender)


@receiver(nav_event_settings, dispatch_uid="venueless_nav_settings")
def navbar_info(sender, request, **kwargs):
    url = resolve(request.path_info)

    if not request.user.has_perm("orga.change_settings", request.event):
        return []

    return [
        {
            "label": _("Eventyay video"),
            "url": reverse(
                "plugins:pretalx_venueless:settings",
                kwargs={
                    "event": request.event.slug,
                },
            ),
            "active": url.namespace == "plugins:pretalx_venueless"
            and url.url_name == "settings",
        }
    ]


@receiver(html_above_profile_page, dispatch_uid="venueless_profile_page_join")
def profile_page_join(sender, request, **kwargs):
    return render_join_link(sender, request)


@receiver(html_above_submission_list, dispatch_uid="venueless_submission_page_join")
def submission_page_join(sender, request, **kwargs):
    return render_join_link(sender, request)


def render_join_link(event, request):
    venueless_settings = getattr(event, "venueless_settings", None)
    if (
        request.user.is_anonymous
        or not event.talks.filter(speakers__in=[request.user]).exists()
        or not venueless_settings
        or not venueless_settings.secret
        or not venueless_settings.show_join_link
    ):
        return

    template = get_template("pretalx_venueless/join_link.html")
    ctx = {
        "event": event,
        "user": request.user,
    }
    return template.render(ctx, request=request)
