import string

from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, TemplateView, View

from pretalx.common.mail import mail
from pretalx.common.views import ActionFromUrl, CreateOrUpdateView
from pretalx.event.models import Event
from pretalx.orga.authorization import OrgaPermissionRequired
from pretalx.orga.forms import EventForm
from pretalx.orga.forms.event import MailSettingsForm
from pretalx.person.forms import UserForm
from pretalx.person.models import EventPermission, User


class EventDetail(OrgaPermissionRequired, ActionFromUrl, CreateOrUpdateView):
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

    def get_initial(self):
        initial = super().get_initial()
        initial['permissions'] = User.objects.filter(
            permissions__is_orga=True,
            permissions__event=self.object
        )
        return initial

    def form_valid(self, form):
        messages.success(self.request, _('Yay!'))
        ret = super().form_valid(form)
        return ret


class EventMailSettings(OrgaPermissionRequired, ActionFromUrl, FormView):
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


class EventTeam(OrgaPermissionRequired, TemplateView):
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


class EventTeamInvite(OrgaPermissionRequired, View):

    def post(self, request, event):
        email = request.POST.get('email')
        event = self.request.event
        invitation_token = get_random_string(
            allowed_chars=string.ascii_lowercase + string.digits, length=20
        )
        EventPermission.objects.create(
            event=event,
            invitation_email=email,
            invitation_token=invitation_token,
            is_orga=True,
        )
        return redirect(reverse(
            'orga:settings.team.view',
            kwargs={'event': event.slug}
        ))


class EventTeamRetract(OrgaPermissionRequired, View):

    def dispatch(self, request, event, pk):
        EventPermission.objects.filter(event__slug=event, pk=pk).delete()
        return redirect(reverse('orga:settings.team.view', kwargs={'event': event}))


class EventTeamDelete(OrgaPermissionRequired, View):

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
        if EventPermission.objects.filter(user=user, event=permission.event).exists():
            permission.delete()
            permission = EventPermission.objects.filter(user=user, event=permission.event)
            permission.is_orga = True

        permission.user = user
        permission.save()
        login(self.request, user)
        return redirect(reverse('orga:event.dashboard', kwargs={'event': permission.event.slug}))
