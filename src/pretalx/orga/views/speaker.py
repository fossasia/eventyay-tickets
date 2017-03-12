from django.core.urlresolvers import reverse
from django.views.generic import ListView

from pretalx.common.views import ActionFromUrl, CreateOrUpdateView
from pretalx.orga.authorization import OrgaPermissionRequired
from pretalx.orga.forms import SpeakerForm
from pretalx.person.models import User


class SpeakerList(OrgaPermissionRequired, ListView):
    template_name = 'orga/speaker/list.html'
    context_object_name = 'speakers'
    model = User

    def get_queryset(self):
        return User.objects\
            .filter(submissions__in=self.request.event.submissions.all())\
            .order_by('id')\
            .distinct()


class SpeakerDetail(OrgaPermissionRequired, ActionFromUrl, CreateOrUpdateView):
    template_name = 'orga/speaker/form.html'
    form_class = SpeakerForm
    model = User

    def get_object(self):
        return User.objects\
            .filter(submissions__in=self.request.event.submissions.all())\
            .order_by('id')\
            .distinct()\
            .get(pk=self.kwargs['pk'])

    def get_success_url(self) -> str:
        return reverse('orga:speakers.view', kwargs={'event': self.request.event.slug, 'pk': self.object.pk})

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['submission_count'] = User.objects.filter(submissions__in=self.request.event.submissions.all()).count()
        return ctx
