from csp.decorators import csp_update
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView, ListView, View

from pretalx.common.mail import SendMailException
from pretalx.common.mixins.views import (
    ActionFromUrl, Filterable, PermissionRequired, Sortable,
)
from pretalx.common.views import CreateOrUpdateView
from pretalx.person.forms import (
    SpeakerFilterForm, SpeakerInformationForm, SpeakerProfileForm,
)
from pretalx.person.models import SpeakerInformation, SpeakerProfile, User
from pretalx.submission.forms import QuestionsForm
from pretalx.submission.models.submission import SubmissionStates


class SpeakerList(PermissionRequired, Sortable, Filterable, ListView):
    model = SpeakerProfile
    template_name = 'orga/speaker/list.html'
    context_object_name = 'speakers'
    default_filters = ('user__email__icontains', 'user__name__icontains')
    sortable_fields = ('user__email', 'user__name')
    default_sort_field = 'user__name'
    paginate_by = 25
    permission_required = 'orga.view_speakers'

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['filter_form'] = SpeakerFilterForm()
        return context

    def get_queryset(self):
        qs = SpeakerProfile.objects.filter(event=self.request.event, user__in=self.request.event.submitters)

        qs = self.filter_queryset(qs)
        if 'role' in self.request.GET:
            if self.request.GET['role'] == 'true':
                qs = qs.filter(
                    user__submissions__state__in=[
                        SubmissionStates.ACCEPTED,
                        SubmissionStates.CONFIRMED,
                    ]
                )
            elif self.request.GET['role'] == 'false':
                qs = qs.exclude(
                    user__submissions__state__in=[
                        SubmissionStates.ACCEPTED,
                        SubmissionStates.CONFIRMED,
                    ]
                )

        qs = qs.order_by('id').distinct()
        qs = self.sort_queryset(qs)
        return qs


@method_decorator(csp_update(IMG_SRC="https://www.gravatar.com"), name='dispatch')
class SpeakerDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    template_name = 'orga/speaker/form.html'
    form_class = SpeakerProfileForm
    model = User
    permission_required = 'orga.view_speaker'
    write_permission_required = 'orga.change_speaker'

    def get_object(self):
        return get_object_or_404(
            User.objects.filter(
                Q(submissions__in=self.request.event.submissions.all())
                | Q(
                    submissions__in=self.request.event.submissions(
                        manager='deleted_objects'
                    ).all()
                )
            )
            .order_by('id')
            .distinct(),
            pk=self.kwargs['pk'],
        )

    @cached_property
    def object(self):
        return self.get_object()

    def get_permission_object(self):
        return self.object.event_profile(self.request.event)

    @cached_property
    def permission_object(self):
        return self.get_permission_object()

    def get_success_url(self) -> str:
        return reverse(
            'orga:speakers.view',
            kwargs={'event': self.request.event.slug, 'pk': self.kwargs['pk']},
        )

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        submissions = self.request.event.submissions.filter(speakers__in=[self.object])
        context['submission_count'] = submissions.count()
        context['submissions'] = submissions
        context['questions_form'] = self.questions_form
        return context

    @cached_property
    def questions_form(self):
        speaker = self.get_object()
        return QuestionsForm(
            self.request.POST if self.request.method == 'POST' else None,
            files=self.request.FILES if self.request.method == 'POST' else None,
            target='speaker',
            speaker=speaker,
            event=self.request.event,
        )

    @transaction.atomic()
    def form_valid(self, form):
        result = super().form_valid(form)
        self.questions_form.speaker = self.get_object()
        if not self.questions_form.is_valid():
            return self.get(self.request, *self.args, **self.kwargs)
        self.questions_form.save()
        if form.has_changed():
            self.get_object().event_profile(self.request.event).log_action(
                'pretalx.user.profile.update', person=self.request.user, orga=True
            )
        messages.success(self.request, 'The speaker profile has been updated.')
        return result

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'event': self.request.event, 'user': self.object})
        return kwargs


class SpeakerPasswordReset(PermissionRequired, DetailView):
    permission_required = 'orga.change_speaker'
    template_name = 'orga/speaker/reset_password.html'
    model = User
    context_object_name = 'speaker'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = self.get_object().event_profile(self.request.event)
        return context

    def get_permission_object(self):
        return self.request.event

    @transaction.atomic()
    def post(self, request, *args, **kwargs):
        user = self.get_object()
        try:
            user.reset_password(
                event=getattr(self.request, 'event', None), user=self.request.user
            )
            messages.success(
                self.request, _('The password was reset and the user was notified.')
            )
        except SendMailException:
            messages.error(
                self.request,
                _(
                    'The password reset email could not be sent, so the password was not reset.'
                ),
            )
        return redirect(user.event_profile(self.request.event).orga_urls.base)


class SpeakerToggleArrived(PermissionRequired, View):
    permission_required = 'orga.change_speaker'

    def get_object(self):
        return get_object_or_404(
            SpeakerProfile, event=self.request.event, user_id=self.kwargs['pk']
        )

    @cached_property
    def object(self):
        return self.get_object()

    def dispatch(self, request, event, pk):
        profile = self.object
        profile.has_arrived = not profile.has_arrived
        profile.save()
        action = (
            'pretalx.speaker.arrived'
            if profile.has_arrived
            else 'pretalx.speaker.unarrived'
        )
        profile.user.log_action(
            action,
            data={'event': self.request.event.slug},
            person=self.request.user,
            orga=True,
        )
        if request.GET.get('from') == 'list':
            return redirect(
                reverse('orga:speakers.list', kwargs={'event': self.kwargs['event']})
            )
        return redirect(reverse('orga:speakers.view', kwargs=self.kwargs))


class InformationList(PermissionRequired, ListView):
    queryset = SpeakerInformation.objects.order_by('pk')
    template_name = 'orga/speaker/information_list.html'
    context_object_name = 'information'
    paginate_by = 25
    permission_required = 'orga.view_information'

    def get_permission_object(self):
        return self.request.event


class InformationDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    template_name = 'orga/speaker/information_form.html'
    form_class = SpeakerInformationForm
    model = SpeakerInformation
    permission_required = 'orga.view_information'
    write_permission_required = 'orga.change_information'

    def get_permission_object(self):
        return self.get_object() or self.request.event

    def get_object(self):
        if 'pk' in self.kwargs:
            return self.request.event.information.filter(pk=self.kwargs['pk']).first()
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.pop('read_only', None)
        return kwargs

    def form_valid(self, form):
        if not hasattr(form.instance, 'event') or not form.instance.event:
            form.instance.event = self.request.event
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.event.orga_urls.information


class InformationDelete(PermissionRequired, DetailView):
    model = SpeakerInformation
    permission_required = 'orga.change_information'
    template_name = 'orga/speaker/information_delete.html'

    def post(self, request, *args, **kwargs):
        information = self.get_object()
        information.delete()
        messages.success(request, _('The information has been deleted.'))
        return redirect(request.event.orga_urls.information)
