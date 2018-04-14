from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView, ListView, UpdateView

from pretalx.common.mixins.views import PermissionRequired
from pretalx.common.views import CreateOrUpdateView
from pretalx.event.forms import TeamForm, TeamInviteForm
from pretalx.event.models import Organiser, Team, TeamInvite


class TeamMixin:

    def get_queryset(self):
        return Team.objects.filter(
            Q(all_events=True) | Q(limit_events__in=[self.request.event]),
            organiser=self.request.event.organiser,
        )


class Teams(PermissionRequired, TeamMixin, ListView):
    template_name = 'orga/settings/team_list.html'
    context_object_name = 'teams'
    permission_required = 'orga.change_team_settings'

    def get_permission_object(self):
        return self.request.event


class TeamDetail(PermissionRequired, TeamMixin, CreateOrUpdateView):
    template_name = 'orga/settings/team_detail.html'
    form_class = TeamForm
    model = Team
    permission_required = 'orga.change_team_settings'

    def get_permission_object(self):
        return self.request.event

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super().get_form_kwargs(*args, **kwargs)
        kwargs['user'] = self.request.user
        return kwargs

    def get_object(self):
        if 'pk' not in self.kwargs:
            return None
        return self.get_queryset().filter(pk=self.kwargs.get('pk')).first()

    @cached_property
    def invite_form(self):
        is_bound = self.request.method == 'POST' and self.request.POST.get('form') == 'invite'
        return TeamInviteForm(self.request.POST if is_bound else None)

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['team'] = self.object
        ctx['invite_form'] = self.invite_form
        return ctx

    def post(self, *args, **kwargs):
        if self.invite_form.is_bound:
            if self.invite_form.is_valid():
                invite = TeamInvite.objects.create(team=self.get_object(), email=self.invite_form.cleaned_data['email'])
                invite.send(event=self.request.event)
                messages.success(self.request, _('The invitation has been generated, it\'s in the outbox.'))
                return redirect(self.request.path)
            else:
                return self.form_invalid(*args, **kwargs)
            return redirect(self.request.path)
        return super().post(*args, **kwargs)

    def form_valid(self, form, *args, **kwargs):
        created = not bool(form.instance.pk)
        form.save()
        messages.success(self.request, _('The settings have been saved.'))
        if created:
            return redirect(self.request.event.orga_urls.team_settings)
        return redirect(self.request.path)


class TeamDelete(PermissionRequired, TeamMixin, DetailView):
    template_name = 'orga/settings/team_delete.html'
    permission_required = 'orga.change_team_settings'

    def get_permission_object(self):
        return self.request.event

    @cached_property
    def team(self):
        return get_object_or_404(Team, pk=self.kwargs['pk'])

    def get_object(self):
        if 'user_pk' in self.kwargs:
            return self.team.members.filter(pk=self.kwargs.get('user_pk')).first()
        return self.team

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['team'] = self.team
        ctx['member'] = self.get_object()
        if ctx['member'] == ctx['team']:
            ctx['member'] = None
        return ctx

    def post(self, request, *args, **kwargs):
        if 'user_pk' in self.kwargs:
            self.team.members.remove(self.get_object())
            messages.success(request, _('The member was removed from the team.'))
        else:
            self.get_object().delete()
            messages.success(request, _('The team was removed.'))
        return redirect(self.request.event.orga_urls.team_settings)


class TeamUninvite(PermissionRequired, DetailView):
    model = TeamInvite
    template_name = 'orga/settings/team_delete.html'
    permission_required = 'orga.change_team_settings'

    def get_permission_object(self):
        return self.request.event

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['team'] = self.object.team
        ctx['member'] = self.object
        return ctx

    def post(self, request, *args, **kwargs):
        self.get_object().delete()
        messages.success(request, _('The team invitation was retracted.'))
        return redirect(self.request.event.orga_urls.team_settings)


class OrganiserDetail(PermissionRequired, UpdateView):
    model = Organiser
    permission_required = 'orga.change_organiser_settings'

    def get_permission_object(self):
        return self.request.event
