import string

from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, TemplateView, View

from pretalx.common.mail import mail_send_task
from pretalx.common.urls import build_absolute_uri
from pretalx.common.views import ActionFromUrl, CreateOrUpdateView
from pretalx.event.models import Event
from pretalx.orga.forms import EventForm
from pretalx.orga.forms.event import MailSettingsForm
from pretalx.person.forms import LoginInfoForm, UserForm, OrgaProfileForm
from pretalx.person.models import EventPermission, User
from pretalx.schedule.forms import RoomForm
from pretalx.schedule.models import Room


class EventDetail(ActionFromUrl, CreateOrUpdateView):
    model = Event
    form_class = EventForm
    template_name = 'orga/settings/form.html'

    def dispatch(self, request, *args, **kwargs):
        if self._action == 'create':
            if not request.user.is_anonymous and not request.user.is_superuser:
                raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        return Event.objects.get(slug=self.kwargs.get('event'))

    def get_success_url(self) -> str:
        return reverse('orga:settings.event.view', kwargs={'event': self.object.slug})

    def form_valid(self, form):
        new_event = not bool(form.instance.pk)
        ret = super().form_valid(form)
        if new_event:
            messages.success(self.request, _('Yay, a new event! Check the settings and configure a CfP and you\'re good to go!'))
            form.instance.log_action('pretalx.event.create', person=self.request.user, orga=True)
            EventPermission.objects.create(
                event=form.instance,
                user=self.request.user,
                is_orga=True,
            )
        else:
            form.instance.log_action('pretalx.event.update', person=self.request.user, orga=True)
            messages.success(self.request, _('The event settings have been saved.'))
        return ret


class EventMailSettings(ActionFromUrl, FormView):
    form_class = MailSettingsForm
    template_name = 'orga/settings/mail.html'

    def get_success_url(self) -> str:
        return reverse('orga:settings.mail.view', kwargs={'event': self.request.event.slug})

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


class EventTeam(TemplateView):
    template_name = 'orga/settings/team.html'

    def get_object(self):
        return Event.objects.get(slug=self.kwargs.get('event'))

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        event = self.get_object()
        ctx['team'] = User.objects.filter(
            permissions__is_orga=True,
            permissions__event=event,
        )
        ctx['pending'] = EventPermission.objects.filter(event=event, user__isnull=True, is_orga=True)
        return ctx


class EventTeamInvite(View):

    def post(self, request, event):
        email = request.POST.get('email')
        event = request.event
        invitation_token = get_random_string(allowed_chars=string.ascii_lowercase + string.digits, length=20)
        invitation_link = build_absolute_uri('orga:invitation.view', kwargs={'code': invitation_token})
        EventPermission.objects.create(
            event=event,
            invitation_email=email,
            invitation_token=invitation_token,
            is_orga=True,
        )
        invitation_text = _('''Hi!

You have been invited to the orga crew of {event} - Please click here to accept:

    {invitation_link}

See you there,
The {event} orga crew (minus you)''').format(event=event.name, invitation_link=invitation_link)
        mail_send_task.apply_async(args=(
            [email],
            _('You have been invited to the orga crew of {event}').format(event=request.event.name),
            invitation_text,
            request.event.email,
            event.pk
        ))
        request.event.log_action('pretalx.event.invite.orga.send', person=request.user, orga=True)
        messages.success(
            request,
            _('<{email}> has been invited to your team - more team members help distribute the workload, so … yay!').format(email=email)
        )
        return redirect(reverse(
            'orga:settings.team.view',
            kwargs={'event': event.slug}
        ))


class EventTeamRetract(View):

    def dispatch(self, request, event, pk):
        EventPermission.objects.filter(event__slug=event, pk=pk).delete()
        request.event.log_action('pretalx.event.invite.orga.retract', person=request.user, orga=True)
        return redirect(reverse('orga:settings.team.view', kwargs={'event': event}))


class EventTeamDelete(View):

    def dispatch(self, request, event, pk):
        EventPermission.objects.filter(event__slug=event, user__id=pk).update(is_orga=False)
        return redirect(reverse('orga:settings.team.view', kwargs={'event': event}))


class InvitationView(FormView):
    template_name = 'orga/invitation.html'
    form_class = UserForm

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['invitation'] = EventPermission.objects.get(
            invitation_token=self.kwargs.get('code'),
        )

        return ctx

    def form_valid(self, form):
        form.save()
        permission = EventPermission.objects.get(invitation_token=self.kwargs.get('code'))
        user = User.objects.get(pk=form.cleaned_data.get('user_id'))

        permission.is_orga = True
        permission.user = user
        permission.save()
        permission.event.log_action('pretalx.event.invite.orga.accept', person=user, orga=True)
        login(self.request, user)
        return redirect(reverse('orga:event.dashboard', kwargs={'event': permission.event.slug}))


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


class RoomList(TemplateView):
    template_name = 'orga/settings/room_list.html'


class RoomDelete(View):

    def dispatch(self, request, event, pk):
        request.event.rooms.get(pk=pk).delete()
        messages.success(self.request, _('Room deleted. Hopefully nobody was still in there …'))
        return redirect(reverse('orga:settings.rooms.list', kwargs={'event': request.event.slug}))


class RoomDetail(ActionFromUrl, CreateOrUpdateView):
    model = Room
    form_class = RoomForm
    template_name = 'orga/settings/room_form.html'

    def get_object(self):
        try:
            return self.request.event.rooms.get(pk=self.kwargs['pk'])
        except (Room.DoesNotExist, KeyError):
            return

    def get_success_url(self) -> str:
        return reverse('orga:settings.rooms.list', kwargs={'event': self.request.event.slug})

    def form_valid(self, form):
        created = not bool(form.instance.pk)
        form.instance.event = self.request.event
        ret = super().form_valid(form)
        messages.success(self.request, _('Saved!'))
        if created:
            form.instance.log_action('pretalx.room.create', person=self.request.user, orga=True)
        else:
            form.instance.log_action('pretalx.event.update', person=self.request.user, orga=True)
        return ret
