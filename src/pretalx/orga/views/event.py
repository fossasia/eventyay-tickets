import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, TemplateView, UpdateView
from formtools.wizard.views import SessionWizardView
from pytz import timezone
from rest_framework.authtoken.models import Token

from pretalx.common.mixins.views import ActionFromUrl, PermissionRequired
from pretalx.common.tasks import regenerate_css
from pretalx.common.views import is_form_bound
from pretalx.event.forms import (
    EventWizardBasicsForm, EventWizardCopyForm, EventWizardDisplayForm,
    EventWizardInitialForm, EventWizardTimelineForm,
)
from pretalx.event.models import Event, Team, TeamInvite
from pretalx.orga.forms import EventForm, EventSettingsForm
from pretalx.orga.forms.event import MailSettingsForm
from pretalx.orga.signals import activate_event
from pretalx.person.forms import LoginInfoForm, OrgaProfileForm, UserForm
from pretalx.person.models import User


class EventSettingsPermission(PermissionRequired):
    permission_required = 'orga.change_settings'

    def get_permission_object(self):
        return self.request.event


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

    @cached_property
    def sform(self):
        return EventSettingsForm(
            read_only=(self._action == 'view'),
            locales=self.request.event.locales,
            obj=self.request.event,
            attribute_name='settings',
            data=self.request.POST if self.request.method == "POST" else None,
            prefix='settings',
        )

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['sform'] = self.sform
        context['url_placeholder'] = f'https://{self.request.host}/'
        return context

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
        context = super().get_context_data(**kwargs)
        warnings = []
        suggestions = []
        if not self.request.event.cfp.text or len(str(self.request.event.cfp.text)) < 50:
            warnings.append({'text': _('The CfP doesn\'t have a full text yet.'), 'url': self.request.event.cfp.urls.text})
        if not self.request.event.landing_page_text or len(str(self.request.event.landing_page_text)) < 50:
            warnings.append({'text': _('The event doesn\'t have a landing page text yet.'), 'url': self.request.event.orga_urls.settings})
        # TODO: test that mails can be sent
        if not self.request.event.submission_types.count() > 1:
            suggestions.append({'text': _('You have configured only one submission type so far.'), 'url': self.request.event.cfp.urls.types})
        if not self.request.event.questions.exists():
            suggestions.append({'text': _('You have configured no questions yet.'), 'url': self.request.event.cfp.urls.new_question})
        context['warnings'] = warnings
        context['suggestions'] = suggestions
        return context

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
                    messages.success(request, _('This event is now hidden.'))
        elif action == 'deactivate':
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

    @cached_property
    def object(self):
        return get_object_or_404(TeamInvite, token__iexact=self.kwargs.get('code'))

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['invitation'] = self.object
        return context

    @transaction.atomic()
    def form_valid(self, form):
        form.save()
        invite = self.object
        user = User.objects.filter(pk=form.cleaned_data.get('user_id')).first()
        if not user:
            messages.error(
                self.request,
                _(
                    'There was a problem with your authentication. Please contact the organiser for further help.'
                ),
            )
            return redirect(self.request.event.urls.base)

        invite.team.members.add(user)
        invite.team.save()

        invite.team.organiser.log_action(
            'pretalx.invite.orga.accept', person=user, orga=True
        )
        messages.info(self.request, _('You are now part of the team!'))
        invite.delete()

        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('/orga')


class UserSettings(TemplateView):
    form_class = LoginInfoForm
    template_name = 'orga/user.html'

    def get_success_url(self) -> str:
        return reverse('orga:user.view')

    @cached_property
    def login_form(self):
        return LoginInfoForm(
            user=self.request.user,
            data=self.request.POST if is_form_bound(self.request, 'login') else None,
        )

    @cached_property
    def profile_form(self):
        return OrgaProfileForm(
            instance=self.request.user,
            data=self.request.POST if is_form_bound(self.request, 'profile') else None,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['token'] = Token.objects.filter(
            user=self.request.user
        ).first() or Token.objects.create(user=self.request.user)
        context['login_form'] = self.login_form
        context['profile_form'] = self.profile_form
        return context

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


class EventWizard(PermissionRequired, SessionWizardView):
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

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form, **kwargs)
        context['has_organiser'] = (
            self.request.user.teams.filter(can_create_events=True).exists()
            or self.request.user.is_administrator
        )
        context['url_placeholder'] = f'https://{self.request.host}/'
        if self.steps.current != 'initial':
            context['organiser'] = self.get_cleaned_data_for_step('initial').get(
                'organiser'
            )
        return context

    def render(self, form=None, **kwargs):
        if self.steps.current != 'initial':
            fdata = self.get_cleaned_data_for_step('initial')
            if fdata is None:
                return self.render_goto_step('initial')
        return super().render(form, **kwargs)

    def get_form_kwargs(self, step=None):
        kwargs = {'user': self.request.user}
        if step != 'initial':
            fdata = self.get_cleaned_data_for_step('initial')
            kwargs.update(fdata)
        return kwargs

    @transaction.atomic()
    def done(self, form_list, form_dict, *args, **kwargs):
        initial = self.get_cleaned_data_for_step('initial')
        basics = self.get_cleaned_data_for_step('basics')
        timeline = self.get_cleaned_data_for_step('timeline')
        display = self.get_cleaned_data_for_step('display')
        copy = self.get_cleaned_data_for_step('copy')

        event = Event.objects.create(
            organiser=initial['organiser'],
            locale_array=','.join(initial['locales']),
            name=basics['name'],
            slug=basics['slug'],
            timezone=basics['timezone'],
            email=basics['email'],
            locale=basics['locale'],
            primary_color=display['primary_color'],
            logo=display['logo'],
            date_from=timeline['date_from'],
            date_to=timeline['date_to'],
        )
        deadline = timeline.get('deadline')
        if deadline:
            zone = timezone(event.timezone)
            deadline = zone.localize(deadline.replace(tzinfo=None))
            event.cfp.deadline = deadline
            event.cfp.save()
        for setting in ['custom_domain', 'display_header_data', 'show_on_dashboard']:
            value = display.get(setting)
            if value:
                event.settings.set(setting, display.get(setting))

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

        if copy and copy['copy_from_event']:
            from_event = copy['copy_from_event']
            event.copy_data_from(from_event)

        return redirect(event.orga_urls.base + '?congratulations')
