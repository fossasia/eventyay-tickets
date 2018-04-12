from csp.decorators import csp_update
from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, TemplateView
from rest_framework.authtoken.models import Token

from pretalx.common.mixins.views import ActionFromUrl, PermissionRequired
from pretalx.common.tasks import regenerate_css
from pretalx.common.views import CreateOrUpdateView
from pretalx.event.models import Event, TeamInvite
from pretalx.orga.forms import EventForm, EventSettingsForm
from pretalx.orga.forms.event import MailSettingsForm
from pretalx.person.forms import LoginInfoForm, OrgaProfileForm, UserForm
from pretalx.person.models import User


class EventSettingsPermission(PermissionRequired):
    permission_required = 'orga.change_settings'

    def get_permission_object(self):
        return self.request.event


class EventDetail(ActionFromUrl, CreateOrUpdateView):
    model = Event
    form_class = EventForm
    write_permission_required = 'orga.change_settings'

    @cached_property
    def _action(self):
        if 'event' not in self.kwargs:
            return 'create'
        if self.request.user.has_perm(self.write_permission_required, self.object):
            return 'edit'
        return 'view'

    def get_template_names(self):
        if self._action == 'create':
            return 'orga/settings/create_event.html'
        return 'orga/settings/form.html'

    def dispatch(self, request, *args, **kwargs):
        if self._action == 'create':
            if not request.user.is_anonymous and not request.user.is_administrator:
                raise PermissionDenied()
        else:
            if not request.user.has_perm('orga.change_settings', self.object):
                raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        return self.object

    @cached_property
    def object(self):
        try:
            return self.request.event
        except AttributeError:
            return

    @cached_property
    def sform(self):
        if not hasattr(self.request, 'event') or not self.request.event:
            return
        return EventSettingsForm(
            read_only=(self._action == 'view'),
            locales=self.request.event.locales,
            obj=self.request.event,
            attribute_name='settings',
            data=self.request.POST if self.request.method == "POST" else None,
            prefix='settings'
        )

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['sform'] = self.sform
        context['url_placeholder'] = f'https://{self.request.host}/'
        return context

    def get_success_url(self) -> str:
        return self.object.orga_urls.settings

    def form_valid(self, form):
        new_event = not bool(form.instance.pk)
        if not new_event:
            if not self.sform.is_valid():
                return self.form_invalid(form)

        ret = super().form_valid(form)

        if new_event:
            url = form.instance.cfp.urls.base
            messages.success(self.request, _('Yay, a new event! Check these settings and <a href="{url}">configure a CfP</a> and you\'re good to go!').format(url=url))
            form.instance.log_action('pretalx.event.create', person=self.request.user, orga=True)
            # TODO: check / create team(s)
        else:
            self.sform.save()
            form.instance.log_action('pretalx.event.update', person=self.request.user, orga=True)
            messages.success(self.request, _('The event settings have been saved.'))
        regenerate_css.apply_async(args=(form.instance.pk,))
        return ret


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
                messages.warning(self.request, _('An error occured while contacting the SMTP server: %s') % str(e))
                return redirect(self.request.event.orga_urls.mail_settings)
            else:
                if form.cleaned_data.get('smtp_use_custom'):
                    messages.success(self.request, _('Yay, your changes have been saved and the connection attempt to '
                                                     'your SMTP server was successful.'))
                else:
                    messages.success(self.request, _('We\'ve been able to contact the SMTP server you configured. '
                                                     'Remember to check the "use custom SMTP server" checkbox, '
                                                     'otherwise your SMTP server will not be used.'))
        else:
            messages.success(self.request, _('Yay! We saved your changes.'))

        ret = super().form_valid(form)
        return ret


@method_decorator(csp_update(SCRIPT_SRC="'self' 'unsafe-inline'"), name='dispatch')
class InvitationView(FormView):
    template_name = 'orga/invitation.html'
    form_class = UserForm

    @cached_property
    def object(self):
        return get_object_or_404(TeamInvite, token__iexact=self.kwargs.get('code'))

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['invitation'] = self.object
        return ctx

    @transaction.atomic()
    def form_valid(self, form):
        form.save()
        invite = self.object
        user = User.objects.filter(pk=form.cleaned_data.get('user_id')).first()
        if not user:
            messages.error(self.request, _('There was a problem with your authentication. Please contact the organiser for further help.'))
            return redirect(self.request.event.urls.base)

        invite.team.members.add(user)
        invite.team.save()

        invite.team.organiser.log_action('pretalx.invite.orga.accept', person=user, orga=True)
        messages.info(self.request, _('You are now part of the team!'))
        invite.delete()

        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('/orga')


@method_decorator(csp_update(SCRIPT_SRC="'self' 'unsafe-inline'"), name='dispatch')
class UserSettings(TemplateView):
    form_class = LoginInfoForm
    template_name = 'orga/user.html'

    def get_success_url(self) -> str:
        return reverse('orga:user.view')

    @cached_property
    def login_form(self):
        bind = self.request.method == 'POST' and self.request.POST.get('form') == 'login'
        return LoginInfoForm(
            user=self.request.user,
            data=self.request.POST if bind else None
        )

    @cached_property
    def profile_form(self):
        bind = self.request.method == 'POST' and self.request.POST.get('form') == 'profile'
        return OrgaProfileForm(
            instance=self.request.user,
            data=self.request.POST if bind else None
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['token'] = Token.objects.filter(user=self.request.user).first() or Token.objects.create(user=self.request.user)
        ctx['login_form'] = self.login_form
        ctx['profile_form'] = self.profile_form
        return ctx

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
            messages.success(request, _('Your API token has been regenerated. The previous token will not be usable any longer.'))
        else:
            messages.error(self.request, _('Oh :( We had trouble saving your input. See below for details.'))
        return redirect(self.get_success_url())
