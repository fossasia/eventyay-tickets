from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import resolve

from pretalx.event.models import Event
from pretalx.person.models import EventPermission


class EventPermissionMiddleware:
    UNAUTHENTICATED = (
        'invitation.view',
        'login',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        url = resolve(request.path_info)

        event_slug = url.kwargs.get('event')
        if event_slug:
            try:
                request.event = Event.objects.get(slug=event_slug)
            except Event.DoesNotExist:
                request.event = None

            if hasattr(request, 'event') and not request.user.is_anonymous:
                request.is_orga = request.user.is_superuser or EventPermission.objects.filter(
                    user=request.user,
                    event=request.event,
                    is_orga=True
                ).exists()

        if not request.user.is_anonymous:
            if request.user.is_superuser:
                request.orga_events = Event.objects.all()
            else:
                request.orga_events = Event.objects.filter(
                    permissions__user=request.user,
                    permissions__is_orga=True,
                )

        if 'orga' in url.namespaces:
            if request.user.is_anonymous and url.url_name not in self.UNAUTHENTICATED:
                return redirect('orga:login')
            if hasattr(request, 'event') and not request.is_orga:
                raise PermissionDenied()

        return self.get_response(request)
