from django.core.exceptions import PermissionDenied

from pretalx.event.models import Event
from pretalx.person.models import EventPermission


class OrgaPermissionRequired:
    login_url = 'orga:login'

    def dispatch(self, request, *args, **kwargs):
        event_slug = kwargs.get('event')

        if event_slug:
            try:
                request.event = Event.objects.get(slug=event_slug)
            except Event.DoesNotExist:
                raise PermissionDenied()

            is_permitted = EventPermission.objects.filter(
                user=request.user,
                event=request.event,
                is_orga=True,
            ).exists()

            if not is_permitted:
                raise PermissionDenied()

        return super().dispatch(request, *args, **kwargs)
