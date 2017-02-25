from django.contrib import messages
from django.core.urlresolvers import reverse
from django.views.generic import DetailView
from django.views.generic.edit import CreateView

from pretalx.event.models import Event
from pretalx.orga.authorization import OrgaPermissionRequired
from pretalx.orga.forms import EventForm


class EventCreate(OrgaPermissionRequired, CreateView):
    model = Event
    form_class = EventForm
    template_name = 'orga/event/create.html'
    context_object_name = 'event'

    def get_success_url(self) -> str:
        return reverse('orga:event.detail', kwargs={'slug': self.kwargs['slug']})

    def form_valid(self, form):
        messages.succes(self.request, 'Yay!')
        ret = super().form_valid(form)
        return ret


class EventDetail(OrgaPermissionRequired, DetailView):
    model = Event
    slug_field = 'slug'
    form_class = EventForm
    template_name = 'orga/event/detail.html'
