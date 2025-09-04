from django.dispatch import receiver

from eventyay.agenda.signals import html_above_session_pages, html_below_session_pages


@receiver(html_above_session_pages, dispatch_uid="html_above_sessions_settings")
def add_html_above_session_pages(sender, request, submission, **kwargs):
    from eventyay.base.templatetags.rich_text import rich_text

    text = request.event.display_settings.get("texts", {}).get(
        "agenda_session_above", ""
    )
    if text:
        return rich_text(text)
    return ""


@receiver(html_below_session_pages, dispatch_uid="html_above_sessions_settings")
def add_html_below_session_pages(sender, request, submission, **kwargs):
    from eventyay.base.templatetags.rich_text import rich_text

    text = request.event.display_settings.get("texts", {}).get(
        "agenda_session_below", ""
    )
    if text:
        return rich_text(text)
    return ""
