from django.dispatch import receiver

from pretalx.agenda.signals import html_above_session_pages, html_below_session_pages
from pretalx.common.templatetags.rich_text import rich_text


@receiver(html_above_session_pages, dispatch_uid="html_above_sessions_settings")
def add_html_above_session_pages(sender, request, submission, **kwargs):
    text = request.event.display_settings.get("texts", {}).get(
        "agenda_session_above", ""
    )
    if text:
        return rich_text(text)
    return ""


@receiver(html_below_session_pages, dispatch_uid="html_above_sessions_settings")
def add_html_below_session_pages(sender, request, submission, **kwargs):
    text = request.event.display_settings.get("texts", {}).get(
        "agenda_session_below", ""
    )
    if text:
        return rich_text(text)
    return ""
