from django.conf import settings
from django.utils.module_loading import import_string

from pretalx.orga.signals import html_head, nav_event, nav_event_settings, nav_global

SessionStore = import_string(f"{settings.SESSION_ENGINE}.SessionStore")


def collect_signal(signal, kwargs):
    result = []
    for _, response in signal.send_robust(**kwargs):
        if isinstance(response, list):
            result += response
        else:
            result.append(response)
    return result


def orga_events(request):
    """Add data to all template contexts."""
    context = {"settings": settings}

    if not request.path.startswith("/orga/"):
        return {}

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return context

    if not getattr(request, "event", None):
        context["nav_global"] = [
            entry
            for entry in collect_signal(
                nav_global, {"sender": None, "request": request}
            )
            if entry
        ]
        return context

    _nav_event = []
    for _, response in nav_event.send_robust(request.event, request=request):
        _nav_event += response if (response and isinstance(response, list)) else []

    context["nav_event"] = _nav_event
    context["nav_settings"] = collect_signal(
        nav_event_settings, {"sender": request.event, "request": request}
    )
    context["html_head"] = "".join(
        collect_signal(html_head, {"sender": request.event, "request": request})
    )

    if (
        not request.event.is_public
        and request.event.custom_domain
        and request.user.has_perm("cfp.view_event", request.event)
    ):
        child_session_key = f"child_session_{request.event.pk}"
        child_session = request.session.get(child_session_key)
        s = SessionStore()
        if not child_session or not s.exists(child_session):
            s[f"pretalx_event_access_{request.event.pk}"] = request.session.session_key
            s.create()
            context["new_session"] = s.session_key
            request.session[child_session_key] = s.session_key
            request.session["event_access"] = True
        else:
            context["new_session"] = child_session
            request.session["event_access"] = True

    return context
