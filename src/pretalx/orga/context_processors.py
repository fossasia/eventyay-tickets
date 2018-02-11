from django.conf import settings

from pretalx.orga.signals import nav_event


def orga_events(request):
    """
    Adds data to all template contexts
    """

    _nav_event = []
    if getattr(request, 'event', None) and hasattr(request, 'user') and request.user.is_authenticated:
        for receiver, response in nav_event.send(request.event, request=request):
            _nav_event += response

    return {
        'nav_event': _nav_event,
        'settings': settings,
    }
