from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import ListView, View

from pretalx.common.mixins.views import (
    ActionFromUrl, Filterable, PermissionRequired, Sortable,
)
from pretalx.common.views import CreateOrUpdateView
from pretalx.person.forms import SpeakerProfileForm
from pretalx.person.models import SpeakerProfile, User


class SpeakerList(PermissionRequired, Sortable, Filterable, ListView):
    model = SpeakerProfile
    template_name = 'orga/speaker/list.html'
    context_object_name = 'speakers'
    default_filters = ('user__nick__icontains', 'user__email__icontains', 'user__name__icontains')
    sortable_fields = ('user__nick', 'user__email', 'user__name')
    default_sort_field = 'user__name'
    paginate_by = 25
    permission_required = 'orga.view_speakers'

    def get_permission_object(self):
        return self.request.event

    def get_queryset(self):
        qs = SpeakerProfile.objects.filter(event=self.request.event)
        qs = self.filter_queryset(qs)
        qs = self.sort_queryset(qs)
        return qs


class SpeakerDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    template_name = 'orga/speaker/form.html'
    form_class = SpeakerProfileForm
    model = User
    permission_required = 'orga.view_speaker'
    write_permission_required = 'orga.change_speaker'

    def get_object(self):
        return get_object_or_404(
            User.objects.filter(submissions__in=self.request.event.submissions.all()).order_by('id').distinct(),
            pk=self.kwargs['pk'],
        )

    def get_permission_object(self):
        return self.get_object().profiles.filter(event=self.request.event).first()

    @property
    def permission_object(self):
        return self.get_permission_object()

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
            profile = self.get_object().profiles.filter(event=self.request.event).first()
            if profile:
                profile.log_action('pretalx.user.profile.update', person=self.request.user, orga=True)
        return super().form_valid(form)

    def get_form_kwargs(self, *args, **kwargs):
        ret = super().get_form_kwargs(*args, **kwargs)
        ret.update({
            'event': self.request.event,
            'user': self.get_object(),
        })
        return ret


class SpeakerToggleArrived(PermissionRequired, View):
    permission_required = 'orga.change_speaker'

    def get_object(self):
        return get_object_or_404(SpeakerProfile, event=self.request.event, user_id=self.kwargs['pk'])

    def dispatch(self, request, event, pk):
        profile = self.get_object()
        profile.has_arrived = not profile.has_arrived
        profile.save()
        action = 'pretalx.speaker.arrived' if profile.has_arrived else 'pretalx.speaker.unarrived'
        profile.user.log_action(action, data={'event': self.request.event.slug}, person=self.request.user, orga=True)
        if request.GET.get('from') == 'list':
            return redirect(reverse('orga:speakers.list', kwargs={'event': self.kwargs['event']}))
        return redirect(reverse(
            'orga:speakers.view',
            kwargs=self.kwargs,
        ))
