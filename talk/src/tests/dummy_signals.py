from django.dispatch import receiver

from pretalx.cfp.signals import footer_link, html_above_profile_page, html_head
from pretalx.common.signals import register_locales
from pretalx.orga.signals import (
    activate_event,
    nav_event,
    nav_event_settings,
    nav_global,
)
from pretalx.submission.signals import submission_state_change


@receiver(register_locales)
def register_locales_test(sender, **kwargs):
    return [("testlocale", "Test")]


@receiver(footer_link)
def footer_link_test(sender, request, **kwargs):
    event = getattr(request, "event", None)
    link = f"/{event.slug}/test" if event else "/test"
    return [{"link": link, "label": "test"}]


@receiver(html_head)
def html_head_test(sender, request, **kwargs):
    if sender.slug != "ignore_signal":
        return '<meta property="pretalx:foo" content="bar">'


@receiver(html_above_profile_page)
def html_above_profile_page_test(sender, request, **kwargs):
    if sender.slug != "ignore_signal":
        return "<p></p>"


@receiver(nav_event_settings)
def nav_event_settings_test(sender, request, **kwargs):
    return []


@receiver(nav_event)
def nav_event_test(sender, request, **kwargs):
    return []


@receiver(nav_global)
def nav_global_test(sender, request, **kwargs):
    return {"label": "root", "url": "/"}


@receiver(activate_event)
def activate_event_test(sender, request, **kwargs):
    if sender.slug == "donottakelive":
        raise Exception("It's not safe to go alone take this")


@receiver(submission_state_change)
def submission_state_change_test(sender, submission, **kwargs):
    submission._state_change_called = getattr(submission, "_state_change_called", 0) + 1
    submission.event.settings.submission_state_change_called = submission.code
