from django.http import Http404
from django.views.generic import TemplateView

from pretalx.event.models import Event


class EventPageMixin:

    def dispatch(self, request, *args, **kwargs):
        event_slug = kwargs.get('event')

        if event_slug:
            try:
                request.event = Event.objects.get(slug=event_slug)
            except Event.DoesNotExist:
                raise Http404()

            if not request.event.is_public:
                raise Http404()

        return super().dispatch(request, *args, **kwargs)


class EventStartpage(EventPageMixin, TemplateView):
    template_name = 'cfp/event/index.html'
