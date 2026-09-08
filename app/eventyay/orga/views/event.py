from datetime import timedelta

from csp.decorators import csp_update
from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.forms.models import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, ListView, TemplateView, UpdateView, View
from django_context_decorator import context

from eventyay.agenda.views.utils import get_schedule_exporters
from eventyay.base.models import Event, LogEntry, ReviewPhase, ReviewScoreCategory, TeamInvite, User
from eventyay.base.models.base import CachedFile
from eventyay.common.forms import I18nEventFormSet, I18nFormSet
from eventyay.common.text.phrases import phrases
from eventyay.common.views.mixins import (
    ActionConfirmMixin,
    ActionFromUrl,
    EventPermissionRequired,
    PermissionRequired,
)
from eventyay.orga.forms import EventForm
from eventyay.orga.forms.event import (
    MailSettingsForm,
    ReviewPhaseForm,
    ReviewScoreCategoryForm,
    ReviewSettingsForm,
    FeedbackSettingsForm,
    ScheduleHtmlExportForm,
    WidgetGenerationForm,
    WidgetSettingsForm,
)
from eventyay.orga.forms.feedback import FeedbackExportForm
from eventyay.orga.forms.importers import CSVImportForm
from eventyay.orga.forms.review import ReviewExportForm
from eventyay.orga.forms.schedule import ScheduleExportForm
from eventyay.orga.forms.speaker import SpeakerExportForm
from eventyay.person.forms import UserForm
from eventyay.submission.tasks import recalculate_all_review_scores

from .speaker import SpeakerImportProcessView
from .submission import SubmissionImportProcessView


class EventSettingsPermission(EventPermissionRequired):
    permission_required = 'base.update_event'
    write_permission_required = 'base.update_event'

    @property
    def permission_object(self):
        return self.request.event


class EventDetail(EventSettingsPermission, ActionFromUrl, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'orga/settings/form.html'

    def get_object(self, queryset=None):
        return self.object

    @cached_property
    def object(self):
        return self.request.event

    def get_form_kwargs(self, *args, **kwargs):
        response = super().get_form_kwargs(*args, **kwargs)
        response['is_administrator'] = self.request.user.is_administrator
        return response

    @context
    def tablist(self):
        return {
            'general': _('General settings'),
        }

    def get_success_url(self) -> str:
        return self.object.orga_urls.settings

    @transaction.atomic
    def form_valid(self, form):
        result = super().form_valid(form)

        form.instance.log_action('eventyay.event.update', person=self.request.user, orga=True)
        messages.success(self.request, phrases.base.saved)
        return result


class EventLive(View):
    def _central_url(self, request):
        return reverse(
            'eventyay_common:event.live',
            kwargs={
                'organizer': request.event.organizer.slug,
                'event': request.event.slug,
            },
        )

    def get(self, request, *args, **kwargs):
        return redirect(self._central_url(request))

    def post(self, request, *args, **kwargs):
        return redirect(self._central_url(request))


class EventHistory(EventSettingsPermission, ListView):
    template_name = 'orga/event/history.html'
    model = LogEntry
    context_object_name = 'log_entries'
    paginate_by = 200

    def get_queryset(self):
        return LogEntry.objects.filter(event=self.request.event)


class EventReviewSettings(EventSettingsPermission, ActionFromUrl, FormView):
    form_class = ReviewSettingsForm
    template_name = 'orga/settings/review.html'

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.review_settings

    @context
    def tablist(self):
        return {
            'general': _('Review settings'),
            'scores': _('Review scoring'),
            'phases': _('Review phases'),
        }

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.request.event
        kwargs['attribute_name'] = 'settings'
        kwargs['locales'] = self.request.event.locales
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        try:
            phases = self.save_phases()
            scores = self.save_scores()
        except ValidationError as e:
            messages.error(self.request, e.message)
            return self.get(self.request, *self.args, **self.kwargs)
        if not phases or not scores:
            messages.error(self.request, phrases.base.error_saving_changes)
            return self.get(self.request, *self.args, **self.kwargs)
        form.save()
        if self.scores_formset.has_changed():
            recalculate_all_review_scores.apply_async(
                kwargs={'event_id': self.request.event.pk},
                ignore_result=True,
            )
        messages.success(self.request, phrases.base.saved)
        return super().form_valid(form)

    @context
    @cached_property
    def phases_formset(self):
        formset_class = inlineformset_factory(
            Event,
            ReviewPhase,
            form=ReviewPhaseForm,
            formset=I18nFormSet,
            can_delete=True,
            extra=0,
        )
        return formset_class(
            self.request.POST if self.request.method == 'POST' else None,
            queryset=ReviewPhase.objects.filter(event=self.request.event).select_related('event'),
            event=self.request.event,
            prefix='phase',
        )

    def save_phases(self):
        if not self.phases_formset.is_valid():
            return False

        with transaction.atomic():
            for form in self.phases_formset.initial_forms:
                # Deleting is handled elsewhere, so we skip it here
                if form.has_changed():
                    form.instance.event = self.request.event
                    form.save()

            extra_forms = [
                form
                for form in self.phases_formset.extra_forms
                if form.has_changed() and not self.phases_formset._should_delete_form(form)
            ]
            for form in extra_forms:
                form.instance.event = self.request.event
                form.save()

            for form in self.phases_formset.deleted_forms:
                form.instance.delete()

            # Now that everything is saved, check for overlapping review phases,
            # and show an error message if any exist. Raise an exception to
            # get out of the transaction.
            self.request.event.reorder_review_phases()
            review_phases = list(self.request.event.review_phases.all().order_by('position'))
            for phase, next_phase in zip(review_phases, review_phases[1:]):
                if not phase.end:
                    raise ValidationError(_('Only the last review phase may be open-ended.'))
                if not next_phase.start:
                    raise ValidationError(_('All review phases except for the first one need a start date.'))
                if phase.end > next_phase.start:
                    raise ValidationError(
                        _(
                            "The review phases '{phase1}' and '{phase2}' overlap. "
                            'Please make sure that review phases do not overlap, then save again.'
                        ).format(phase1=phase.name, phase2=next_phase.name)
                    )
        return True

    @context
    @cached_property
    def scores_formset(self):
        formset_class = inlineformset_factory(
            Event,
            ReviewScoreCategory,
            form=ReviewScoreCategoryForm,
            formset=I18nEventFormSet,
            can_delete=True,
            extra=0,
        )
        return formset_class(
            self.request.POST if self.request.method == 'POST' else None,
            queryset=ReviewScoreCategory.objects.filter(event=self.request.event)
            .select_related('event')
            .prefetch_related('scores'),
            event=self.request.event,
            prefix='scores',
        )

    def save_scores(self):
        if not self.scores_formset.is_valid():
            return False
        weights_changed = False
        for form in self.scores_formset.initial_forms:
            if self.scores_formset._should_delete_form(form):
                continue
            if form.has_changed():
                if 'weight' in form.changed_data:
                    weights_changed = True
                form.instance.event = self.request.event
                form.save()

        extra_forms = [
            form
            for form in self.scores_formset.extra_forms
            if form.has_changed() and not self.scores_formset._should_delete_form(form)
        ]
        for form in extra_forms:
            form.instance.event = self.request.event
            form.save()

        for form in self.scores_formset.deleted_forms:
            if not form.instance.is_independent:
                weights_changed = True
            if form.instance.pk:
                form.instance.scores.all().delete()
                form.instance.delete()

        if weights_changed:
            ReviewScoreCategory.recalculate_scores(self.request.event)
        return True


class FeedbackSettings(EventSettingsPermission, ActionFromUrl, FormView):
    form_class = FeedbackSettingsForm
    template_name = 'orga/settings/feedback.html'

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.feedback_settings

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.request.event
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        form.save()
        messages.success(self.request, phrases.base.saved)
        return super().form_valid(form)


class PhaseActivate(EventSettingsPermission, View):
    def get_object(self):
        return get_object_or_404(ReviewPhase, event=self.request.event, pk=self.kwargs.get('pk'))

    def post(self, request, *args, **kwargs):
        phase = self.get_object()
        phase.activate()
        return redirect(request.event.orga_urls.review_settings)


class EventMailSettings(EventSettingsPermission, ActionFromUrl, FormView):
    form_class = MailSettingsForm
    template_name = 'orga/settings/mail.html'

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.mail_settings

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.request.event
        kwargs['locales'] = self.request.event.locales
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, phrases.base.saved)
        return super().form_valid(form)


class InvitationView(FormView):
    template_name = 'orga/invitation.html'
    form_class = UserForm

    @context
    @cached_property
    def invitation(self):
        return get_object_or_404(TeamInvite, token__iexact=self.kwargs.get('code'))

    @context
    def password_reset_link(self):
        return reverse('orga:auth.reset')

    def post(self, *args, **kwargs):
        if not self.request.user.is_anonymous:
            self.accept_invite(self.request.user)
            return redirect(reverse('eventyay_common:dashboard'))
        return super().post(*args, **kwargs)

    def form_valid(self, form):
        form.save()
        user = User.objects.filter(pk=form.cleaned_data.get('user_id')).first()
        if not user:
            messages.error(
                self.request,
                _('There was a problem with your authentication. Please contact the organizer for further help.'),
            )
            return redirect(self.request.event.urls.base)

        self.accept_invite(user)
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect(reverse('eventyay_common:dashboard'))

    @transaction.atomic()
    def accept_invite(self, user):
        invite = self.invitation
        invite.team.members.add(user)
        invite.team.save()
        invite.team.organizer.log_action('eventyay.invite.orga.accept', person=user, orga=True)
        messages.info(self.request, _('You are now part of the team!'))
        invite.delete()


class EventDelete(PermissionRequired, ActionConfirmMixin, TemplateView):
    permission_required = 'base.administrator_user'
    model = Event
    action_text = (
        _(
            'ALL related data, such as proposals, speaker profiles, and '
            'uploads, will also be deleted and cannot be restored.'
        )
        + ' '
        + phrases.base.delete_warning
    )
    template_name = 'orga/settings/delete_confirm.html'

    def get_object(self):
        return self.request.event

    def action_object_name(self):
        return _('Event') + f': {self.get_object().name}'

    @property
    def action_back_url(self):
        return self.get_object().orga_urls.settings

    def post(self, request, *args, **kwargs):
        if request.POST.get('event_name_confirm') != str(self.get_object().name):
            messages.error(self.request, _('The event name you entered was incorrect.'))
            return redirect(self.request.path)
        self.get_object().shred(person=self.request.user)
        messages.success(self.request, _('The event has been deleted.'))
        return redirect(reverse('eventyay_common:dashboard'))


class EventDeleteTalkData(PermissionRequired, ActionConfirmMixin, TemplateView):
    permission_required = 'base.administrator_user'
    model = Event
    action_text = (
        _(
            'ALL related data, such as proposals, speaker profiles, and '
            'uploads, will also be deleted and cannot be restored.'
        )
        + ' '
        + phrases.base.delete_warning
    )
    template_name = 'orga/settings/delete_confirm.html'

    def get_object(self):
        return self.request.event

    def action_object_name(self):
        return _('Talk Data for') + f' {self.get_object().name}'

    @property
    def action_back_url(self):
        return self.get_object().orga_urls.settings

    def post(self, request, *args, **kwargs):
        if request.POST.get('event_name_confirm') != str(self.get_object().name):
            messages.error(self.request, _('The event name you entered was incorrect.'))
            return redirect(self.request.path)
        self.get_object().delete_talk_data()
        self.get_object().log_action('eventyay.event.talk_data.deleted', person=self.request.user, orga=True)
        messages.success(self.request, _('Talk data has been successfully deleted.'))
        url = reverse(
            'eventyay_common:event.update', 
            kwargs={'organizer': self.request.organizer.slug, 'event': self.get_object().slug}
        ) + '#danger-zone-tab'
        return redirect(url)

@method_decorator(csp_update({'SCRIPT_SRC': "'self' 'unsafe-eval'"}), name='dispatch')
class WidgetSettings(EventSettingsPermission, FormView):
    form_class = WidgetSettingsForm
    template_name = 'orga/settings/widget.html'

    def form_valid(self, form):
        form.save()
        messages.success(self.request, phrases.base.saved)
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.request.event
        return kwargs

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result['extra_form'] = WidgetGenerationForm(instance=self.request.event)
        return result

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.widget_settings


class TargetChoice(models.TextChoices):
    SPEAKER = 'speaker', _('Speakers')
    SCHEDULE = 'session', _('Schedule')

    @classmethod
    def import_target_items(cls):
        return (
            (
                cls.SPEAKER,
                {
                    'filename': SpeakerImportProcessView.IMPORT_FILENAME,
                    'process_url_name': f'orga:{SpeakerImportProcessView.import_process_url_name}',
                },
            ),
            (
                cls.SCHEDULE,
                {
                    'filename': SubmissionImportProcessView.IMPORT_FILENAME,
                    'process_url_name': f'orga:{SubmissionImportProcessView.import_process_url_name}',
                },
            ),
        )

    @classmethod
    def import_choices(cls):
        return tuple((target, target.label) for target, _config in cls.import_target_items())

    @classmethod
    def import_targets(cls):
        return {target: config for target, config in cls.import_target_items()}


class ExportTargetChoice(models.TextChoices):
    SPEAKER = 'speaker', _('Speakers')
    SCHEDULE = 'session', _('Schedule')
    REVIEW = 'review', _('Reviews')
    FEEDBACK = 'feedback', _('Attendee feedback')

    @classmethod
    def export_choices(cls):
        return tuple((target, target.label) for target in cls)


class ImportExportSettings(EventSettingsPermission, TemplateView):
    template_name = 'orga/settings/import_export.html'
    import_choices = TargetChoice.import_choices()
    import_targets = TargetChoice.import_targets()
    export_choices = ExportTargetChoice.export_choices()

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result['event'] = self.request.event
        result['tablist'] = {
            'import': _('Import'),
            'export': _('Export'),
            'schedule_html_export': _('Schedule HTML export'),
        }
        result['active_tab'] = kwargs.get('active_tab')
        result['import_choices'] = self.import_choices
        result['export_choices'] = self.export_choices
        result['import_target'] = kwargs.get('import_target') or self.request.GET.get('import_target') or TargetChoice.SPEAKER
        result['export_target'] = kwargs.get('export_target') or self.request.GET.get('export_target') or ExportTargetChoice.SPEAKER
        result['import_form'] = kwargs.get('import_form') or CSVImportForm()
        result['speaker_export_form'] = kwargs.get('speaker_export_form') or SpeakerExportForm(
            event=self.request.event,
            prefix='speaker',
        )
        result['session_export_form'] = kwargs.get('session_export_form') or ScheduleExportForm(
            event=self.request.event,
            prefix='session',
        )
        result['review_export_form'] = kwargs.get('review_export_form') or ReviewExportForm(
            event=self.request.event,
            user=self.request.user,
            prefix='review',
        )
        result['feedback_export_form'] = kwargs.get('feedback_export_form') or FeedbackExportForm(
            event=self.request.event,
            prefix='feedback',
        )
        result['schedule_html_export_form'] = kwargs.get('schedule_html_export_form') or ScheduleHtmlExportForm(
            obj=self.request.event,
        )
        all_exporters = get_schedule_exporters(self.request)
        result['speaker_exporters'] = [e for e in all_exporters if e.group == 'speaker']
        result['session_exporters'] = [e for e in all_exporters if e.group != 'speaker']
        return result

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')

        # Support for legacy schedule export payloads without prefix
        if not action and 'export_format' in request.POST:
            mutable_post = request.POST.copy()
            mutable_post['action'] = 'export'
            mutable_post['export_target'] = TargetChoice.SCHEDULE.value
            for key, value in request.POST.lists():
                mutable_post.setlist(f'session-{key}', value)
            request.POST = mutable_post
            action = 'export'

        if action == 'import':
            return self.handle_import()
        if action == 'export':
            return self.handle_export()
        if action == 'save_schedule_html_export':
            return self.handle_save_schedule_html_export()
        messages.error(request, _('Unknown action. Please try again.'))
        return redirect(request.path)

    def handle_import(self):
        import_target = self.request.POST.get('import_target', TargetChoice.SPEAKER)
        import_form = CSVImportForm(self.request.POST, self.request.FILES)

        try:
            target = TargetChoice(import_target)
        except ValueError:
            messages.error(self.request, _('Please choose whether to import speakers or schedule.'))
            context = self.get_context_data(import_form=import_form, import_target=import_target)
            return self.render_to_response(context, status=400)

        if not import_form.is_valid():
            context = self.get_context_data(import_form=import_form, import_target=target)
            return self.render_to_response(context, status=400)

        session = self.request.session
        if not session.session_key:
            session.save()
        if not session.session_key:
            messages.error(self.request, _('Could not establish a session for file upload. Please try again.'))
            return redirect(f'{self.request.path}#tab-import')

        target_config = self.import_targets[target]
        import_filename = target_config['filename']
        cached_file = CachedFile.objects.create(
            expires=now() + timedelta(days=1),
            date=now(),
            filename=import_filename,
            type='text/csv',
            web_download=False,
            session_key=session.session_key,
        )
        cached_file.file.save(import_filename, import_form.cleaned_data['file'])
        process_url = reverse(
            target_config['process_url_name'],
            kwargs={'organizer': self.request.event.organizer.slug, 'event': self.request.event.slug, 'file': cached_file.id},
        )
        return redirect(process_url)

    def handle_export(self):
        export_target = self.request.POST.get('export_target', ExportTargetChoice.SPEAKER)

        try:
            target = ExportTargetChoice(export_target)
        except ValueError:
            messages.error(self.request, _('Please choose a valid export target.'))
            context = self.get_context_data(export_target=ExportTargetChoice.SPEAKER, active_tab='export')
            return self.render_to_response(context, status=400)

        speaker_kwargs = {'event': self.request.event, 'prefix': 'speaker'}
        session_kwargs = {'event': self.request.event, 'prefix': 'session'}
        review_kwargs = {'event': self.request.event, 'user': self.request.user, 'prefix': 'review'}
        feedback_kwargs = {'event': self.request.event, 'prefix': 'feedback'}

        if target == ExportTargetChoice.SPEAKER:
            speaker_kwargs['data'] = self.request.POST
        elif target == ExportTargetChoice.SCHEDULE:
            session_kwargs['data'] = self.request.POST
        elif target == ExportTargetChoice.FEEDBACK:
            feedback_kwargs['data'] = self.request.POST
        else:  # ExportTargetChoice.REVIEW
            review_kwargs['data'] = self.request.POST

        speaker_export_form = SpeakerExportForm(**speaker_kwargs)
        session_export_form = ScheduleExportForm(**session_kwargs)
        review_export_form = ReviewExportForm(**review_kwargs)
        feedback_export_form = FeedbackExportForm(**feedback_kwargs)

        active_form = {
            ExportTargetChoice.SPEAKER: speaker_export_form,
            ExportTargetChoice.SCHEDULE: session_export_form,
            ExportTargetChoice.REVIEW: review_export_form,
            ExportTargetChoice.FEEDBACK: feedback_export_form,
        }[target]

        if not active_form.is_valid():
            context = self.get_context_data(
                export_target=target,
                speaker_export_form=speaker_export_form,
                session_export_form=session_export_form,
                review_export_form=review_export_form,
                feedback_export_form=feedback_export_form,
                active_tab='export',
            )
            return self.render_to_response(context, status=400)

        result = active_form.export_data()

        if not result:
            messages.warning(self.request, _('No data to be exported'))
            return redirect(f'{self.request.path}?export_target={target.value}#tab-export')
        return result

    def handle_save_schedule_html_export(self):
        form = ScheduleHtmlExportForm(self.request.POST, obj=self.request.event)
        if form.is_valid():
            form.save()
            self.request.event.log_action(
                'eventyay.event.update', person=self.request.user, orga=True
            )
            messages.success(self.request, phrases.base.saved)
            return redirect(f'{self.request.path}#tab-schedule_html_export')
        context = self.get_context_data(
            schedule_html_export_form=form,
            active_tab='schedule_html_export',
        )
        return self.render_to_response(context, status=400)
