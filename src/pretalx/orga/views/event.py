import string

from csp.decorators import csp_update
from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, TemplateView, View
from rest_framework.authtoken.models import Token

from pretalx.common.mixins.views import ActionFromUrl, PermissionRequired
from pretalx.common.phrases import phrases
from pretalx.common.tasks import regenerate_css
from pretalx.common.urls import build_absolute_uri
from pretalx.common.views import CreateOrUpdateView
from pretalx.event.models import Event
from pretalx.mail.models import QueuedMail
from pretalx.orga.forms import (
    EventForm, EventSettingsForm, ReviewPermissionForm, ReviewSettingsForm,
)
from pretalx.orga.forms.event import MailSettingsForm
from pretalx.person.forms import LoginInfoForm, OrgaProfileForm, UserForm
from pretalx.person.models import EventPermission, User
from pretalx.schedule.forms import RoomForm
from pretalx.schedule.models import Room


class EventSettingsPermission(PermissionRequired):
    permission_required = 'orga.change_settings'

    def get_permission_object(self):
        return self.request.event


class EventDetail(ActionFromUrl, CreateOrUpdateView):
    model = Event
    form_class = EventForm

    def get_template_names(self):
        if self._action == 'create':
            return 'orga/settings/create_event.html'
        return 'orga/settings/form.html'

    def dispatch(self, request, *args, **kwargs):
        if self._action == 'create':
            if not request.user.is_anonymous and not request.user.is_superuser:
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
            messages.success(self.request, _('Yay, a new event! Check these settings and configure a CfP and you\'re good to go!'))
            form.instance.log_action('pretalx.event.create', person=self.request.user, orga=True)
            EventPermission.objects.create(
                event=form.instance,
                user=self.request.user,
                is_orga=True,
            )
        else:
            self.sform.save()
            form.instance.log_action('pretalx.event.update', person=self.request.user, orga=True)
            messages.success(self.request, _('The event settings have been saved.'))
        regenerate_css.apply_async(args=(form.instance.pk,))
        return ret


class EventMailSettings(EventSettingsPermission, ActionFromUrl, FormView):
    form_class = MailSettingsForm
    template_name = 'orga/settings/mail.html'

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
                return redirect(reverse('orga:settings.mail.edit', kwargs={'event': self.request.event.slug}))
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


class EventTeam(EventSettingsPermission, ActionFromUrl, TemplateView):
    template_name = 'orga/settings/team.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        event = self.request.event
        ctx['team'] = User.objects.filter(
            permissions__is_orga=True,
            permissions__event=event,
        )
        ctx['pending'] = EventPermission.objects.filter(event=event, user__isnull=True, is_orga=True)
        return ctx


class EventTeamInvite(EventSettingsPermission, View):

    def _handle_existing_user(self, request, user):
        if user:
            permission = user.permissions.filter(event=request.event).first()
        if not permission:
            EventPermission.objects.create(event=request.event, is_orga=True)
        else:
            permission.is_orga = True
            permission.save(update_fields=['is_orga'])
        invitation_text = _('''Hi!

You have been added to the organizer team of {event}!

We are happy to have you on the team,
The {event} orga crew''').format(event=request.event.name)
        invitation_subject = _('You have been added to the organizer team of {event}').format(event=request.event.name)
        QueuedMail(
            event=request.event, to=user.email, reply_to=request.event.email,
            subject=str(invitation_subject), text=str(invitation_text),
        ).send()
        messages.success(request, _('The user already existed and is now part of the orga.'))
        request.event.log_action('pretalx.invite.orga.send', person=request.user, orga=True)
        return redirect(request.event.orga_urls.team_settings)

    def _handle_new_user(self, request, email, permission=None):
        if not permission:
            invitation_token = get_random_string(allowed_chars=string.ascii_lowercase + string.digits, length=20)
            permission = EventPermission.objects.create(
                event=request.event,
                invitation_email=email,
                invitation_token=invitation_token,
                is_orga=True,
            )
            messages.success(
                request,
                _('<{email}> has been invited to your team - more team members help distribute the workload, so … yay!').format(email=email)
            )
        else:
            permission.is_orga = True
            permission.save()
            invitation_token = permission.invitation_token
            messages.info(
                request,
                _('<{email}> had already been invited – we\'ve resent the invitation instead :)').format(email=email),
            )
        invitation_link = build_absolute_uri('orga:invitation.view', event=request.event, kwargs={'code': invitation_token})
        invitation_text = _('''Hi!

You have been invited to the orga crew of {event} - Please click here to accept:

    {invitation_link}

See you there,
The {event} orga crew (minus you)''').format(event=request.event.name, invitation_link=invitation_link)
        invitation_subject = _('You have been invited to the orga crew of {event}').format(event=request.event.name)
        QueuedMail(
            event=request.event, to=email, reply_to=request.event.email, subject=str(invitation_subject),
            text=str(invitation_text)
        ).send()
        request.event.log_action('pretalx.invite.orga.send', person=request.user, orga=True)
        return redirect(request.event.orga_urls.team_settings)

    def post(self, request, event):
        permission = None
        email = request.POST.get('email')
        user = User.objects.filter(nick__iexact=email).first() or User.objects.filter(email__iexact=email).first()
        if not user:
            kwargs = {
                'event': request.event,
                'invitation_email': email,
            }
            permission = EventPermission.objects.filter(user__isnull=True, **kwargs).first()
        try:
            with transaction.atomic():
                if user:
                    return self._handle_existing_user(request, user)
                elif permission:
                    return self._handle_new_user(request, email, permission=permission)
                elif email:
                    return self._handle_new_user(request, email)
                else:
                    messages.error(request, phrases.common.error_saving_changes)
        except Exception:
            messages.error(request, phrases.base.error_saving_changes)
        return redirect(request.event.orga_urls.team_settings)


class EventTeamRetract(EventSettingsPermission, View):

    def dispatch(self, request, event, pk):
        EventPermission.objects.filter(event=request.event, pk=pk).delete()
        request.event.log_action('pretalx.invite.orga.retract', person=request.user, orga=True)
        return redirect(request.event.orga_urls.team_settings)


class EventTeamDelete(EventSettingsPermission, View):

    def dispatch(self, request, event, pk):
        EventPermission.objects.filter(event=request.event, user__id=pk).update(is_orga=False)
        return redirect(request.event.orga_urls.team_settings)


class EventReview(EventSettingsPermission, ActionFromUrl, FormView):
    form_class = ReviewSettingsForm
    template_name = 'orga/settings/review.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.request.event
        kwargs['attribute_name'] = 'settings'
        kwargs['locales'] = self.request.event.locales
        return kwargs

    def form_valid(self, form):
        ret = super().form_valid(form)
        form.save()
        messages.success(self.request, _('Your settings have been saved.'))
        return ret

    def get_success_url(self) -> str:
        return reverse('orga:settings.review.view', kwargs={'event': self.request.event.slug})


@method_decorator(csp_update(SCRIPT_SRC="'self' 'unsafe-inline'"), name='dispatch')
class InvitationView(FormView):
    template_name = 'orga/invitation.html'
    form_class = UserForm

    @property
    def object(self):
        return get_object_or_404(
            EventPermission,
            invitation_token__iexact=self.kwargs.get('code'),
            user__isnull=True,
        )

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['invitation'] = self.object
        return ctx

    def form_valid(self, form):
        form.save()
        permission = self.object
        user = User.objects.get(pk=form.cleaned_data.get('user_id'))
        perm = EventPermission.objects.filter(user=user, event=permission.event).exclude(pk=permission.pk).first()
        event = permission.event

        if perm:
            if permission.is_orga:
                perm.is_orga = True
            if permission.is_reviewer:
                perm.is_reviewer = True
            perm.save()
            permission.delete()
            permission = perm

        permission.user = user
        permission.save()
        permission.event.log_action('pretalx.invite.orga.accept', person=user, orga=True)
        messages.info(self.request, _('You are now part of the event team!'))

        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect(event.orga_urls.base)


@method_decorator(csp_update(SCRIPT_SRC="'self' 'unsafe-inline'"), name='dispatch')
class UserSettings(TemplateView):
    form_class = LoginInfoForm
    template_name = 'orga/user.html'

    def get_success_url(self) -> str:
        return reverse('orga:user.view')

    @cached_property
    def login_form(self):
        return LoginInfoForm(user=self.request.user,
                             data=(self.request.POST
                                   if self.request.method == 'POST' and self.request.POST.get('form') == 'login'
                                   else None))

    @cached_property
    def profile_form(self):
        return OrgaProfileForm(instance=self.request.user,
                               data=(self.request.POST
                                     if self.request.method == 'POST' and self.request.POST.get('form') == 'profile'
                                     else None))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['token'] = Token.objects.filter(user=self.request.user).first() or Token.objects.create(user=self.request.user)
        ctx['login_form'] = self.login_form
        ctx['profile_form'] = self.profile_form
        return ctx

    def post(self, request, *args, **kwargs):
        if self.login_form.is_bound:
            if self.login_form.is_valid():
                self.login_form.save()
                messages.success(request, _('Your changes have been saved.'))
                request.user.log_action('pretalx.user.password.update')
                return redirect(self.get_success_url())
        elif self.profile_form.is_bound:
            if self.profile_form.is_valid():
                self.profile_form.save()
                messages.success(request, _('Your changes have been saved.'))
                request.user.log_action('pretalx.user.profile.update')
                return redirect(self.get_success_url())

        messages.error(self.request, _('Oh :( We had trouble saving your input. See below for details.'))
        return super().get(request, *args, **kwargs)


class RoomList(EventSettingsPermission, ActionFromUrl, TemplateView):
    template_name = 'orga/settings/room_list.html'


class RoomDelete(EventSettingsPermission, View):
    permission_required = 'orga.edit_room'

    def dispatch(self, request, event, pk):
        try:
            request.event.rooms.get(pk=pk).delete()
            messages.success(self.request, _('Room deleted. Hopefully nobody was still in there …'))
        except ProtectedError:  # TODO: show which/how many talks are concerned
            messages.error(request, _('There is or was a talk scheduled in this room. It cannot be deleted.'))

        return redirect(request.event.orga_urls.room_settings)


class RoomDetail(EventSettingsPermission, ActionFromUrl, CreateOrUpdateView):
    model = Room
    form_class = RoomForm
    template_name = 'orga/settings/room_form.html'
    permission_required = 'orga.view_room'

    def get_object(self):
        try:
            return self.request.event.rooms.get(pk=self.kwargs['pk'])
        except (Room.DoesNotExist, KeyError):
            return

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.room_settings

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super().get_form_kwargs(*args, **kwargs)
        kwargs['event'] = self.request.event
        return kwargs

    def form_valid(self, form):
        form.instance.event = self.request.event

        created = not bool(form.instance.pk)
        if created:
            permission = 'orga.change_settings'
        else:
            permission = 'orga.edit_room'
        if not self.request.user.has_perm(permission, form.instance):
            messages.error(self.request, _('You are not allowed to perform this action, sorry.'))
            return

        ret = super().form_valid(form)
        messages.success(self.request, _('Saved!'))
        if created:
            form.instance.log_action('pretalx.room.create', person=self.request.user, orga=True)
        else:
            form.instance.log_action('pretalx.event.update', person=self.request.user, orga=True)
        return ret
