from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, UpdateView

from pretalx.common.views import ActionFromUrl, CreateOrUpdateView
from pretalx.event.models import Event
from pretalx.orga.authorization import OrgaPermissionRequired
from pretalx.orga.forms import EventForm
from pretalx.person.models import User


class EventDetail(OrgaPermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = Event
    form_class = EventForm
    template_name = 'orga/settings/form.html'

    def dispatch(self, request, *args, **kwargs):
        if self._action == 'create':
            if not request.user.is_anonymous and not request.user.is_superuser:
                raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        return Event.objects.get(slug=self.kwargs.get('event'))

    def get_success_url(self) -> str:
        return reverse('orga:settings.event.view', kwargs={'event': self.object.slug})

    def get_initial(self):
        initial = super().get_initial()
        initial['permissions'] = User.objects.filter(
            permissions__is_orga=True,
            permissions__event=self.object
        )
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'Yay!')
        ret = super().form_valid(form)
        return ret
