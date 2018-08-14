from importlib import import_module

from django.conf import settings

from pretalx.orga.signals import nav_event, nav_global

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


def collect_signal(signal, kwargs):
    result = []
    for receiver, response in signal.send_robust(**kwargs):
        if isinstance(response, dict):
            result.append(response)
    return result


def orga_events(request):
    """Add data to all template contexts."""
    context = {'settings': settings}

    if not request.path.startswith('/orga/'):
        return {}

    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return context

    if not getattr(request, 'event', None):
        context['nav_global'] = collect_signal(
            nav_global, {'sender': None, 'request': request}
        )
        return context

    if (
        getattr(request, 'event', None)
        and hasattr(request, 'user')
        and request.user.is_authenticated
    ):
        context['nav_event'] = collect_signal(
            nav_event, {'sender': request.event, 'request': request}
        )

        if (
            not request.event.is_public
            and request.event.settings.custom_domain
            and request.user.has_perm('cfp.view_event', request.event)
        ):
            child_session_key = f'child_session_{request.event.pk}'
            child_session = request.session.get(child_session_key)
            s = SessionStore()
            if not child_session or not s.exists(child_session):
                s[
                    f'pretalx_event_access_{request.event.pk}'
                ] = request.session.session_key
                s.create()
                context['new_session'] = s.session_key
                request.session[child_session_key] = s.session_key
                request.session['event_access'] = True
            else:
                context['new_session'] = child_session
                request.session['event_access'] = True

    return context
