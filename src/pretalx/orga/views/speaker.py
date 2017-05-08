from django.contrib import messages
from django.core.urlresolvers import reverse
from django.views.generic import ListView

from pretalx.common.views import ActionFromUrl, CreateOrUpdateView
from pretalx.person.forms import SpeakerProfileForm
from pretalx.person.models import User


class SpeakerList(ListView):
    template_name = 'orga/speaker/list.html'
    context_object_name = 'speakers'
    model = User

    def get_queryset(self):
        return User.objects\
            .filter(submissions__in=self.request.event.submissions.all())\
            .order_by('id')\
            .distinct()


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
        return reverse('orga:speakers.view', kwargs={'event': self.request.event.slug, 'pk': self.object.pk})

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['submission_count'] = User.objects.filter(submissions__in=self.request.event.submissions.all()).count()
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
