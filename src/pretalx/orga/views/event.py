import json
import os
from contextlib import suppress

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db.models import Q
from django.forms.models import inlineformset_factory
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DeleteView, FormView, TemplateView, UpdateView, View
from django_context_decorator import context
from formtools.wizard.views import SessionWizardView
from pytz import timezone
from rest_framework.authtoken.models import Token

from pretalx.common.forms import I18nFormSet
from pretalx.common.mixins.views import (
    ActionFromUrl, EventPermissionRequired, PermissionRequired, SensibleBackWizardMixin,
)
from pretalx.common.tasks import regenerate_css
from pretalx.common.views import is_form_bound
from pretalx.event.forms import (
    EventWizardBasicsForm, EventWizardCopyForm, EventWizardDisplayForm,
    EventWizardInitialForm, EventWizardTimelineForm, ReviewPhaseForm,
)
from pretalx.event.models import Event, Team, TeamInvite
from pretalx.orga.forms import EventForm, EventSettingsForm
from pretalx.orga.forms.event import MailSettingsForm, ReviewSettingsForm
from pretalx.orga.signals import activate_event
from pretalx.person.forms import LoginInfoForm, OrgaProfileForm, UserForm
from pretalx.person.models import User
from pretalx.submission.models import ReviewPhase


class EventSettingsPermission(EventPermissionRequired):
    permission_required = 'orga.change_settings'


class EventDetail(ActionFromUrl, EventSettingsPermission, UpdateView):
    model = Event
    form_class = EventForm
    permission_required = 'orga.change_settings'
    template_name = 'orga/settings/form.html'

    def get_object(self):
        return self.object

    @cached_property
    def object(self):
        return self.request.event

    @context
    @cached_property
    def sform(self):
        return EventSettingsForm(
            read_only=(self.action == 'view'),
            locales=self.request.event.locales,
            obj=self.request.event,
            attribute_name='settings',
            data=self.request.POST if self.request.method == "POST" else None,
            prefix='settings',
        )

    def get_form_kwargs(self, *args, **kwargs):
        response = super().get_form_kwargs(*args, **kwargs)
        response['is_administrator'] = self.request.user.is_administrator
        return response

    @context
    def url_placeholder(self):
        return f'https://{self.request.host}/'

    def get_success_url(self) -> str:
        return self.object.orga_urls.settings

    def form_valid(self, form):
        if not self.sform.is_valid():
            return self.form_invalid(form)
        result = super().form_valid(form)

        self.sform.save()
        form.instance.log_action(
            'pretalx.event.update', person=self.request.user, orga=True
        )
        messages.success(self.request, _('The event settings have been saved.'))
        regenerate_css.apply_async(args=(form.instance.pk,))
        return result


class EventLive(EventSettingsPermission, TemplateView):
    template_name = 'orga/event/live.html'
    permission_required = 'orga.change_settings'

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        warnings = []
        suggestions = []
        # TODO: move to signal
        if (
            not self.request.event.cfp.text
            or len(str(self.request.event.cfp.text)) < 50
        ):
            warnings.append(
                {
                    'text': _('The CfP doesn\'t have a full text yet.'),
                    'url': self.request.event.cfp.urls.text,
                }
            )
        if (
            not self.request.event.landing_page_text
            or len(str(self.request.event.landing_page_text)) < 50
        ):
            warnings.append(
                {
                    'text': _('The event doesn\'t have a landing page text yet.'),
                    'url': self.request.event.orga_urls.settings,
                }
            )
        # TODO: test that mails can be sent
        if (
            self.request.event.settings.use_tracks
            and self.request.event.settings.cfp_request_track
            and self.request.event.tracks.count() < 2
        ):
            suggestions.append(
                {
                    'text': _(
                        'You want submitters to choose the tracks for their submissions, but you do not offer tracks for selection. Add at least one track!'
                    ),
                    'url': self.request.event.cfp.urls.tracks,
                }
            )
        if not self.request.event.submission_types.count() > 1:
            suggestions.append(
                {
                    'text': _('You have configured only one submission type so far.'),
                    'url': self.request.event.cfp.urls.types,
                }
            )
        if not self.request.event.questions.exists():
            suggestions.append(
                {
                    'text': _('You have configured no questions yet.'),
                    'url': self.request.event.cfp.urls.new_question,
                }
            )
        result['warnings'] = warnings
        result['suggestions'] = suggestions
        return result

    def post(self, request, *args, **kwargs):
        event = request.event
        action = request.POST.get('action')
        if action == 'activate':
            if event.is_public:
                messages.success(request, _('This event was already live.'))
            else:
                responses = activate_event.send_robust(event, request=request)
                exceptions = [
                    response[1]
                    for response in responses
                    if isinstance(response[1], Exception)
                ]
                if exceptions:
                    messages.error(request, '\n'.join([str(e) for e in exceptions]))
                else:
                    event.is_public = True
                    event.save()
                    event.log_action(
                        'pretalx.event.activate',
                        person=self.request.user,
                        orga=True,
                        data={},
                    )
                    messages.success(request, _('This event is now public.'))
        else:  # action == 'deactivate'
            if not event.is_public:
                messages.success(request, _('This event was already hidden.'))
            else:
                event.is_public = False
                event.save()
                event.log_action(
                    'pretalx.event.deactivate',
                    person=self.request.user,
                    orga=True,
                    data={},
                )
                messages.success(request, _('This event is now hidden.'))
        return redirect(event.orga_urls.base)


class EventReviewSettings(EventSettingsPermission, ActionFromUrl, FormView):
    form_class = ReviewSettingsForm
    template_name = 'orga/settings/review.html'
    write_permission_required = 'orga.change_settings'

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.review_settings

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.request.event
        kwargs['attribute_name'] = 'settings'
        kwargs['locales'] = self.request.event.locales
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        formset = self.save_formset()
        if not formset:
            return self.get(self.request, *self.args, **self.kwargs)
        form.save()
        return super().form_valid(form)

    @context
    @cached_property
    def formset(self):
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
            queryset=ReviewPhase.objects.filter(event=self.request.event),
            event=self.request.event,
        )

    def save_formset(self):
        if not self.formset.is_valid():
            return False
        for form in self.formset.initial_forms:
            # Deleting is handled elsewhere, so we skip it here
            if form.has_changed():
                form.instance.event = self.request.event
                form.save()

        extra_forms = [
            form
            for form in self.formset.extra_forms
            if form.has_changed and not self.formset._should_delete_form(form)
        ]
        for form in extra_forms:
            form.instance.event = self.request.event
            form.save()
        return True


def phase_move(request, pk, up=True):
    try:
        phase = request.event.review_phases.get(pk=pk)
    except ReviewPhase.DoesNotExist:
        raise Http404(_('The selected review phase does not exist.'))
    if not request.user.has_perm('orga.change_settings', phase):
        messages.error(request, _('Sorry, you are not allowed to reorder review phases.'))
        return
    phases = list(request.event.review_phases.order_by('position'))

    index = phases.index(phase)
    if index != 0 and up:
        phases[index - 1], phases[index] = phases[index], phases[index - 1]
    elif index != len(phases) - 1 and not up:
        phases[index + 1], phases[index] = phases[index], phases[index + 1]

    for i, phase in enumerate(phases):
        if phase.position != i:
            phase.position = i
            phase.save()
    messages.success(request, _('The order of review phases has been updated.'))


def phase_move_up(request, event, pk):
    phase_move(request, pk, up=True)
    return redirect(request.event.orga_urls.review_settings)


def phase_move_down(request, event, pk):
    phase_move(request, pk, up=False)
    return redirect(request.event.orga_urls.review_settings)


class PhaseDelete(PermissionRequired, View):
    permission_required = 'orga.change_settings'

    def get_object(self):
        return get_object_or_404(
            ReviewPhase, event=self.request.event, pk=self.kwargs.get('pk')
        )

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        phase = self.get_object()
        phase.delete()
        return redirect(self.request.event.orga_urls.review_settings)


class PhaseActivate(PermissionRequired, View):
    permission_required = 'orga.change_settings'

    def get_object(self):
        return get_object_or_404(
            ReviewPhase, event=self.request.event, pk=self.kwargs.get('pk')
        )

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        phase = self.get_object()
        phase.activate()
        return redirect(self.request.event.orga_urls.review_settings)


class EventMailSettings(EventSettingsPermission, ActionFromUrl, FormView):
    form_class = MailSettingsForm
    template_name = 'orga/settings/mail.html'
    write_permission_required = 'orga.change_settings'

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.mail_settings

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.request.event
        kwargs['attribute_name'] = 'settings'
        kwargs['locales'] = self.request.event.locales
        return kwargs

    def form_valid(self, form):
        form.save()

        if self.request.POST.get('test', '0').strip() == '1':
            backend = self.request.event.get_mail_backend(force_custom=True)
            try:
                backend.test(self.request.event.settings.mail_from)
            except Exception as e:
                messages.warning(
                    self.request,
                    _('An error occurred while contacting the SMTP server: %s')
                    % str(e),
                )
                return redirect(self.request.event.orga_urls.mail_settings)
            else:
                if form.cleaned_data.get('smtp_use_custom'):
                    messages.success(
                        self.request,
                        _(
                            'Yay, your changes have been saved and the connection attempt to '
                            'your SMTP server was successful.'
                        ),
                    )
                else:
                    messages.success(
                        self.request,
                        _(
                            'We\'ve been able to contact the SMTP server you configured. '
                            'Remember to check the "use custom SMTP server" checkbox, '
                            'otherwise your SMTP server will not be used.'
                        ),
                    )
        else:
            messages.success(self.request, _('Yay! We saved your changes.'))

        return super().form_valid(form)


class InvitationView(FormView):
    template_name = 'orga/invitation.html'
    form_class = UserForm

    @context
    @cached_property
    def invitation(self):
        return get_object_or_404(TeamInvite, token__iexact=self.kwargs.get('code'))

    def post(self, *args, **kwargs):
        if not self.request.user.is_anonymous:
            self.accept_invite(self.request.user)
            return redirect('/orga')
        return super().post(*args, **kwargs)

    def form_valid(self, form):
        form.save()
        user = User.objects.filter(pk=form.cleaned_data.get('user_id')).first()
        if not user:
            messages.error(
                self.request,
                _(
                    'There was a problem with your authentication. Please contact the organiser for further help.'
                ),
            )
            return redirect(self.request.event.urls.base)

        self.accept_invite(user)
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('/orga')

    @transaction.atomic()
    def accept_invite(self, user):
        invite = self.invitation
        invite.team.members.add(user)
        invite.team.save()
        invite.team.organiser.log_action(
            'pretalx.invite.orga.accept', person=user, orga=True
        )
        messages.info(self.request, _('You are now part of the team!'))
        invite.delete()


class UserSettings(TemplateView):
    form_class = LoginInfoForm
    template_name = 'orga/user.html'

    def get_success_url(self) -> str:
        return reverse('orga:user.view')

    @context
    @cached_property
    def login_form(self):
        return LoginInfoForm(
            user=self.request.user,
            data=self.request.POST if is_form_bound(self.request, 'login') else None,
        )

    @context
    @cached_property
    def profile_form(self):
        return OrgaProfileForm(
            instance=self.request.user,
            data=self.request.POST if is_form_bound(self.request, 'profile') else None,
        )

    @context
    def token(self):
        return Token.objects.filter(
            user=self.request.user
        ).first() or Token.objects.create(user=self.request.user)

    def post(self, request, *args, **kwargs):
        if self.login_form.is_bound and self.login_form.is_valid():
            self.login_form.save()
            messages.success(request, _('Your changes have been saved.'))
            request.user.log_action('pretalx.user.password.update')
        elif self.profile_form.is_bound and self.profile_form.is_valid():
            self.profile_form.save()
            messages.success(request, _('Your changes have been saved.'))
            request.user.log_action('pretalx.user.profile.update')
        elif request.POST.get('form') == 'token':
            request.user.regenerate_token()
            messages.success(
                request,
                _(
                    'Your API token has been regenerated. The previous token will not be usable any longer.'
                ),
            )
        else:
            messages.error(
                self.request,
                _('Oh :( We had trouble saving your input. See below for details.'),
            )
        return redirect(self.get_success_url())


def condition_copy(wizard):
    return EventWizardCopyForm.copy_from_queryset(wizard.request.user).exists()


class EventWizard(PermissionRequired, SensibleBackWizardMixin, SessionWizardView):
    permission_required = 'orga.create_events'
    file_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, 'new_event')
    )
    form_list = [
        ('initial', EventWizardInitialForm),
        ('basics', EventWizardBasicsForm),
        ('timeline', EventWizardTimelineForm),
        ('display', EventWizardDisplayForm),
        ('copy', EventWizardCopyForm),
    ]
    condition_dict = {'copy': condition_copy}

    def get_template_names(self):
        return f'orga/event/wizard/{self.steps.current}.html'

    @context
    def has_organiser(self):
        return (
            self.request.user.teams.filter(can_create_events=True).exists()
            or self.request.user.is_administrator
        )

    @context
    def url_placeholder(self):
        return f'https://{self.request.host}/'

    @context
    def organiser(self):
        return (
            self.get_cleaned_data_for_step('initial').get('organiser')
            if self.steps.current != 'initial'
            else None
        )

    def render(self, form=None, **kwargs):
        if self.steps.current != 'initial':
            fdata = self.get_cleaned_data_for_step('initial')
            if fdata is None:
                return self.render_goto_step('initial')
        if self.steps.current == 'timeline':
            fdata = self.get_cleaned_data_for_step('basics')
            year = now().year % 100
            if fdata and not str(year) in fdata['slug'] and not str(year + 1) in fdata['slug']:
                messages.warning(self.request, str(_('Please consider including your event\'s year in the slug, e.g. myevent{number}.')).format(number=year))
        if self.steps.current == 'display':
            fdata = self.get_cleaned_data_for_step('timeline')
            if fdata and fdata.get('date_to') < now().date():
                messages.warning(self.request, _('Did you really mean to make your event take place in the past?'))
        return super().render(form, **kwargs)

    def get_form_kwargs(self, step=None):
        kwargs = {'user': self.request.user}
        if step != 'initial':
            fdata = self.get_cleaned_data_for_step('initial')
            kwargs.update(fdata or dict())
        return kwargs

    @transaction.atomic()
    def done(self, form_list, *args, **kwargs):
        steps = {
            step: self.get_cleaned_data_for_step(step)
            for step in ('initial', 'basics', 'timeline', 'display', 'copy')
        }

        event = Event.objects.create(
            organiser=steps['initial']['organiser'],
            locale_array=','.join(steps['initial']['locales']),
            name=steps['basics']['name'],
            slug=steps['basics']['slug'],
            timezone=steps['basics']['timezone'],
            email=steps['basics']['email'],
            locale=steps['basics']['locale'],
            primary_color=steps['display']['primary_color'],
            logo=steps['display']['logo'],
            date_from=steps['timeline']['date_from'],
            date_to=steps['timeline']['date_to'],
        )
        deadline = steps['timeline'].get('deadline')
        if deadline:
            zone = timezone(event.timezone)
            event.cfp.deadline = zone.localize(deadline.replace(tzinfo=None))
            event.cfp.save()
        for setting in ['custom_domain', 'display_header_data', 'show_on_dashboard']:
            value = steps['display'].get(setting)
            if value:
                event.settings.set(setting, value)

        has_control_rights = self.request.user.teams.filter(
            organiser=event.organiser,
            all_events=True,
            can_change_event_settings=True,
            can_change_submissions=True,
        ).exists()
        if not has_control_rights:
            t = Team.objects.create(
                organiser=event.organiser,
                name=_(f'Team {event.name}'),
                can_change_event_settings=True,
                can_change_submissions=True,
            )
            t.members.add(self.request.user)
            t.limit_events.add(event)

        logdata = {}
        for f in form_list:
            logdata.update({k: v for k, v in f.cleaned_data.items()})
        event.log_action(
            'pretalx.event.create', person=self.request.user, data=logdata, orga=True
        )

        if steps['copy'] and steps['copy']['copy_from_event']:
            event.copy_data_from(steps['copy']['copy_from_event'])

        return redirect(event.orga_urls.base + '?congratulations')


class EventDelete(PermissionRequired, DeleteView):
    template_name = 'orga/event/delete.html'
    permission_required = 'person.is_administrator'
    model = Event

    def get_object(self):
        return getattr(self.request, 'event', None)

    def delete(self, request, *args, **kwargs):
        event = self.get_object()
        if event:
            event.shred()
        return redirect('/orga/')


def event_list(request):
    query = json.dumps(str(request.GET.get('query', '')))[1:-1]
    page = 1
    with suppress(ValueError):
        page = int(request.GET.get('page', '1'))
    qs = (
        request.user.get_events_with_any_permission()
        .filter(
            Q(name__icontains=query)
            | Q(slug__icontains=query)
            | Q(organiser__name__icontains=query)
            | Q(organiser__slug__icontains=query)
        )
        .order_by('-date_from')
    )

    total = qs.count()
    pagesize = 20
    offset = (page - 1) * pagesize
    doc = {
        'results': [
            {
                'id': event.pk,
                'slug': event.slug,
                'organiser': str(event.organiser.name),
                'name': str(event.name),
                'text': str(event.name),
                'date_range': event.get_date_range_display(),
                'url': event.orga_urls.base,
            }
            for event in qs.select_related('organiser')[offset: offset + pagesize]
        ],
        'pagination': {"more": total >= (offset + pagesize)},
    }
    return JsonResponse(doc)
