from django.core.urlresolvers import resolve

from pretalx.event.models import Event


def add_events(request):
    if request.resolver_match.namespace == 'orga' and not request.user.is_anonymous:
        try:
            url_name = resolve(request.path_info).url_name
        except:
            url_name = ''
        return {
            'events': [e for e in Event.objects.filter(permissions__is_orga=True, permissions__user=request.user)],
            'url_name': url_name,
        }
    return dict()
