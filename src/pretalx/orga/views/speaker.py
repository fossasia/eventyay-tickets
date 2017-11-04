from django.contrib import messages
from django.urls import reverse
from django.views.generic import ListView

from pretalx.common.views import (
    ActionFromUrl, CreateOrUpdateView, Filterable, Sortable,
)
from pretalx.person.forms import SpeakerProfileForm
from pretalx.person.models import SpeakerProfile, User


class SpeakerList(Sortable, Filterable, ListView):
    template_name = 'orga/speaker/list.html'
    context_object_name = 'speakers'
    default_filters = ('user__nick__icontains', 'user__email__icontains', 'user__name__icontains')
    filter_fields = ('user__nick', 'user__email', 'user__name')
    sortable_fields = ('user__nick', 'user__email', 'user__name')
    paginate_by = 25

    def get_queryset(self):
        qs = SpeakerProfile.objects.filter(event=self.request.event).order_by('user__pk')
        qs = self.filter_queryset(qs)
        qs = self.sort_queryset(qs)
        return qs


class SpeakerDetail(ActionFromUrl, CreateOrUpdateView):
    template_name = 'orga/speaker/form.html'
    form_class = SpeakerProfileForm
    model = User

    def get_object(self):
        return User.objects\
            .filter(submissions__in=self.request.event.submissions.all())\
            .order_by('id')\
            .distinct()\
            .get(pk=self.kwargs['pk'])

    def get_success_url(self) -> str:
        return reverse('orga:speakers.view', kwargs={'event': self.request.event.slug, 'pk': self.get_object().pk})

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        submissions = self.request.event.submissions.filter(speakers__in=[self.get_object()])
        ctx['submission_count'] = submissions.count()
        ctx['submissions'] = submissions
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'The speaker profile has been updated.')
        if form.has_changed():
            profile = self.get_object().profiles.get(event=self.request.event)
            profile.log_action('pretalx.user.profile.update', person=self.request.user, orga=True)
        return super().form_valid(form)

    def get_form_kwargs(self, *args, **kwargs):
        ret = super().get_form_kwargs(*args, **kwargs)
        ret.update({
            'event': self.request.event,
            'user': self.get_object(),
        })
        return ret
