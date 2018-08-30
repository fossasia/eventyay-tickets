from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView, ListView, TemplateView

from pretalx.common.mail import SendMailException
from pretalx.common.mixins.views import PermissionRequired
from pretalx.common.views import CreateOrUpdateView
from pretalx.event.forms import OrganiserForm, TeamForm, TeamInviteForm
from pretalx.event.models import Organiser, Team, TeamInvite


class TeamMixin:
    def get_queryset(self):
        if hasattr(self.request, 'event') and self.request.event:
            return Team.objects.filter(
                Q(all_events=True) | Q(limit_events__in=[self.request.event]),
                organiser=self.request.event.organiser,
            )
        return Team.objects.filter(organiser=getattr(self.request, 'organiser', None))


class Teams(PermissionRequired, TeamMixin, ListView):
    permission_required = 'orga.change_teams'
    template_name = 'orga/settings/team_list.html'
    context_object_name = 'teams'

    def get_permission_object(self):
        return getattr(self.request, 'event', getattr(self.request, 'organiser', None))


class TeamDetail(PermissionRequired, TeamMixin, CreateOrUpdateView):
    permission_required = 'orga.change_teams'
    template_name = 'orga/settings/team_detail.html'
    form_class = TeamForm
    model = Team

    def get_permission_object(self):
        return getattr(self.request, 'event', getattr(self.request, 'organiser', None))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        organiser = None
        if 'pk' not in self.kwargs:
            if self.request.user.is_administrator:
                organiser = Organiser.objects.all()
            else:
                teams = Team.objects.filter(
                    members__in=[self.request.user], can_change_teams=True
                )
                organiser = Organiser.objects.filter(
                    pk__in=teams.values_list('organiser_id', flat=True)
                )
        kwargs['organiser'] = organiser
        return kwargs

    def get_object(self):
        if 'pk' not in self.kwargs:
            return None
        return self.get_queryset().filter(pk=self.kwargs.get('pk')).first()

    @cached_property
    def invite_form(self):
        is_bound = (
            self.request.method == 'POST' and self.request.POST.get('form') == 'invite'
        )
        return TeamInviteForm(self.request.POST if is_bound else None)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['team'] = self.object
        context['invite_form'] = self.invite_form
        return context

    def post(self, *args, **kwargs):
        if self.invite_form.is_bound:
            if self.invite_form.is_valid():
                invite = TeamInvite.objects.create(
                    team=self.get_object(), email=self.invite_form.cleaned_data['email']
                )
                event = getattr(self.request, 'event', None)
                invite.send(event=event)
                if event:
                    messages.success(
                        self.request,
                        _('The invitation has been generated, it\'s in the outbox.'),
                    )
                else:
                    messages.success(self.request, _('The invitation has been sent.'))
            else:
                return self.form_invalid(*args, **kwargs)
            return redirect(self.request.path)
        return super().post(*args, **kwargs)

    def form_valid(self, form, *args, **kwargs):
        created = not bool(form.instance.pk)
        form.save()
        messages.success(self.request, _('The settings have been saved.'))
        if created:
            if hasattr(self.request, 'event') and self.request.event:
                return redirect(self.request.event.orga_urls.team_settings)
            return redirect(self.request.organiser.orga_urls.base)
        return redirect(self.request.path)


class TeamDelete(PermissionRequired, TeamMixin, DetailView):
    permission_required = 'orga.change_teams'
    template_name = 'orga/settings/team_delete.html'

    def get_permission_object(self):
        return getattr(self.request, 'event', getattr(self.request, 'organiser', None))

    @cached_property
    def team(self):
        return get_object_or_404(Team, pk=self.kwargs['pk'])

    def get_object(self):
        if 'user_pk' in self.kwargs:
            return self.team.members.filter(pk=self.kwargs.get('user_pk')).first()
        return self.team

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['team'] = self.team
        context['member'] = self.get_object()
        if context['member'] == context['team']:
            context['member'] = None
        return context

    def post(self, request, *args, **kwargs):
        if 'user_pk' in self.kwargs:
            self.team.members.remove(self.get_object())
            messages.success(request, _('The member was removed from the team.'))
        else:
            self.get_object().delete()
            messages.success(request, _('The team was removed.'))
        if hasattr(self.request, 'event') and self.request.event:
            return redirect(self.request.event.orga_urls.team_settings)
        return redirect(self.request.organiser.orga_urls.base)


class TeamUninvite(PermissionRequired, DetailView):
    model = TeamInvite
    template_name = 'orga/settings/team_delete.html'
    permission_required = 'orga.change_teams'

    def get_permission_object(self):
        return getattr(self.request, 'event', getattr(self.request, 'organiser', None))

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['team'] = self.object.team
        context['member'] = self.object
        return context

    def post(self, request, *args, **kwargs):
        self.get_object().delete()
        messages.success(request, _('The team invitation was retracted.'))
        if hasattr(self.request, 'event') and self.request.event:
            return redirect(self.request.event.orga_urls.team_settings)
        return redirect(self.request.organiser.orga_urls.base)


class TeamResetPassword(PermissionRequired, TemplateView):
    model = Team
    template_name = 'orga/settings/team_reset_password.html'
    permission_required = 'orga.change_teams'

    def get_permission_object(self):
        return getattr(self.request, 'event', getattr(self.request, 'organiser', None))

    @cached_property
    def team(self):
        return get_object_or_404(Team, pk=self.kwargs['pk'])

    @cached_property
    def user(self):
        return get_object_or_404(self.team.members, pk=self.kwargs['user_pk'])

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['team'] = self.team
        context['member'] = self.user
        return context

    def post(self, request, *args, **kwargs):
        try:
            self.user.reset_password(
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
        if hasattr(self.request, 'event') and self.request.event:
            return redirect(self.request.event.orga_urls.team_settings)
        return redirect(self.request.organiser.orga_urls.base)


class OrganiserDetail(PermissionRequired, CreateOrUpdateView):
    template_name = 'orga/organiser_detail.html'
    model = Organiser
    permission_required = 'orga.change_organiser_settings'
    form_class = OrganiserForm

    def get_object(self):
        return self.request.organiser

    def get_success_url(self):
        messages.success(self.request, _('Saved!'))
        return self.request.path
