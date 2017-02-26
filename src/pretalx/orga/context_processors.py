from pretalx.event.models import Event


def add_events(request):
    if request.resolver_match.namespace == 'orga' and not request.user.is_anonymous:
        return {
            'events': [e for e in Event.objects.filter(permissions__is_orga=True, permissions__user=request.user)]
        }
    return dict()
