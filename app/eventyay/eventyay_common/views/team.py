from urllib.parse import urljoin

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import ManyToManyField
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from django_scopes import scopes_disabled

from eventyay.base.auth import get_auth_backends
from eventyay.base.models.organizer import Team, TeamAPIToken, TeamInvite
from eventyay.base.models.auth import User
from eventyay.base.services.mail import SendMailException, mail
from eventyay.control.views.organizer import OrganizerDetailViewMixin
from eventyay.helpers.urls import build_absolute_uri as build_global_uri

from ...control.forms.organizer_forms import TeamForm
from ...control.permissions import OrganizerPermissionRequiredMixin


class TeamListView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView):
    model = Team
    template_name = 'eventyay_common/organizers/teams/teams.html'
    context_object_name = 'teams'
    permission = 'can_change_teams'

    def get_queryset(self):
        return self.request.organizer.teams.all().order_by('name')


class TeamMemberView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DetailView):
    template_name = 'eventyay_common/organizers/teams/team_members.html'
    context_object_name = 'team'
    permission = 'can_change_teams'
    model = Team

    def get_object(self, queryset=None):
        return get_object_or_404(Team, organizer=self.request.organizer, pk=self.kwargs.get('team'))

    @cached_property
    def add_form(self):
        from eventyay.control.views.organizer import InviteForm

        return InviteForm(
            data=(self.request.POST if self.request.method == 'POST' and 'user' in self.request.POST else None)
        )

    @cached_property
    def add_token_form(self):
        from eventyay.control.views.organizer import TokenForm

        return TokenForm(
            data=(self.request.POST if self.request.method == 'POST' and 'name' in self.request.POST else None)
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['add_form'] = self.add_form
        ctx['add_token_form'] = self.add_token_form
        return ctx

    def _send_invite(self, instance):
        try:
            mail(
                instance.email,
                _('eventyay account invitation'),
                'pretixcontrol/email/invitation.txt',
                {
                    'user': self,
                    'organizer': self.request.organizer.name,
                    'team': instance.team.name,
                    'url': build_global_uri('eventyay_common:auth.invite', kwargs={'token': instance.token}),
                },
                event=None,
                locale=self.request.LANGUAGE_CODE,
            )
        except SendMailException:
            pass  # Already logged

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        if 'remove-member' in request.POST:
            try:
                user = User.objects.get(pk=request.POST.get('remove-member'))
            except (User.DoesNotExist, ValueError):
                pass
            else:
                other_admin_teams = (
                    self.request.organizer.teams.exclude(pk=self.object.pk)
                    .filter(can_change_teams=True, members__isnull=False)
                    .exists()
                )
                if not other_admin_teams and self.object.can_change_teams and self.object.members.count() == 1:
                    messages.error(
                        self.request,
                        _(
                            'You cannot remove the last member from this team as no one would '
                            'be left with the permission to change teams.'
                        ),
                    )
                    return redirect(self.get_success_url())
                else:
                    self.object.members.remove(user)
                    self.object.log_action(
                        'eventyay.team.member.removed',
                        user=self.request.user,
                        data={'email': user.email, 'user': user.pk},
                    )
                    messages.success(self.request, _('The member has been removed from the team.'))
                    return redirect(self.get_success_url())

        elif 'remove-invite' in request.POST:
            try:
                invite = self.object.invites.get(pk=request.POST.get('remove-invite'))
            except (TeamInvite.DoesNotExist, ValueError):
                messages.error(self.request, _('Invalid invite selected.'))
                return redirect(self.get_success_url())
            else:
                invite.delete()
                self.object.log_action(
                    'eventyay.team.invite.deleted',
                    user=self.request.user,
                    data={'email': invite.email},
                )
                messages.success(self.request, _('The invite has been revoked.'))
                return redirect(self.get_success_url())

        elif 'resend-invite' in request.POST:
            try:
                invite = self.object.invites.get(pk=request.POST.get('resend-invite'))
            except (TeamInvite.DoesNotExist, ValueError):
                messages.error(self.request, _('Invalid invite selected.'))
                return redirect(self.get_success_url())
            else:
                self._send_invite(invite)
                self.object.log_action(
                    'eventyay.team.invite.resent',
                    user=self.request.user,
                    data={'email': invite.email},
                )
                messages.success(self.request, _('The invite has been resent.'))
                return redirect(self.get_success_url())

        elif 'remove-token' in request.POST:
            try:
                token = self.object.tokens.get(pk=request.POST.get('remove-token'))
            except (TeamAPIToken.DoesNotExist, ValueError):
                messages.error(self.request, _('Invalid token selected.'))
                return redirect(self.get_success_url())
            else:
                token.active = False
                token.save()
                self.object.log_action(
                    'eventyay.team.token.deleted',
                    user=self.request.user,
                    data={'name': token.name},
                )
                messages.success(self.request, _('The token has been revoked.'))
                return redirect(self.get_success_url())

        elif 'user' in self.request.POST and self.add_form.is_valid() and self.add_form.has_changed():
            try:
                user = User.objects.get(email__iexact=self.add_form.cleaned_data['user'])
            except User.DoesNotExist:
                if self.object.invites.filter(email__iexact=self.add_form.cleaned_data['user']).exists():
                    messages.error(
                        self.request,
                        _('This user already has been invited for this team.'),
                    )
                    return self.get(request, *args, **kwargs)
                if 'native' not in get_auth_backends():
                    messages.error(
                        self.request,
                        _('Users need to have a eventyay account before they can be invited.'),
                    )
                    return self.get(request, *args, **kwargs)

                invite = self.object.invites.create(email=self.add_form.cleaned_data['user'])
                self._send_invite(invite)
                self.object.log_action(
                    'eventyay.team.invite.created',
                    user=self.request.user,
                    data={'email': self.add_form.cleaned_data['user']},
                )
                messages.success(self.request, _('The new member has been invited to the team.'))
                return redirect(self.get_success_url())
            else:
                if self.object.members.filter(pk=user.pk).exists():
                    messages.error(
                        self.request,
                        _('This user already has permissions for this team.'),
                    )
                    return self.get(request, *args, **kwargs)

                self.object.members.add(user)
                self.object.log_action(
                    'eventyay.team.member.added',
                    user=self.request.user,
                    data={
                        'email': user.email,
                        'user': user.pk,
                    },
                )
                messages.success(self.request, _('The new member has been added to the team.'))
                return redirect(self.get_success_url())

        elif 'name' in self.request.POST and self.add_token_form.is_valid() and self.add_token_form.has_changed():
            token = self.object.tokens.create(name=self.add_token_form.cleaned_data['name'])
            self.object.log_action(
                'eventyay.team.token.created',
                user=self.request.user,
                data={'name': self.add_token_form.cleaned_data['name'], 'id': token.pk},
            )
            messages.success(
                self.request,
                _(
                    'A new API token has been created with the following secret: {}\n'
                    'Please copy this secret to a safe place. You will not be able to '
                    'view it again here.'
                ).format(token.token),
            )
            return redirect(self.get_success_url())
        else:
            messages.error(self.request, _('Your changes could not be saved.'))
            return self.get(request, *args, **kwargs)

    def get_success_url(self) -> str:
        return reverse(
            'eventyay_common:organizer.team',
            kwargs={'organizer': self.request.organizer.slug, 'team': self.object.pk},
        )


class TeamCreateView(OrganizerDetailViewMixin, CreateView, OrganizerPermissionRequiredMixin):
    model = Team
    template_name = 'eventyay_common/organizers/teams/team_edit.html'
    form_class = TeamForm
    permission = 'can_change_teams'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def get_object(self, queryset=None):
        return get_object_or_404(Team, organizer=self.request.organizer, pk=self.kwargs.get('team'))

    @transaction.atomic
    @scopes_disabled()
    def form_valid(self, form):
        messages.success(
            self.request,
            _('The team has been created. You can now add members to the team.'),
        )
        form.instance.organizer = self.request.organizer
        response = super().form_valid(form)
        form.instance.members.add(self.request.user)
        form.instance.log_action(
            'eventyay.team.created',
            user=self.request.user,
            data={
            k: [e.id for e in getattr(self.object, k).all()] if isinstance(self.model._meta.get_field(k), ManyToManyField) else getattr(self.object, k)
            for k in form.changed_data
        },
        )
        return response

    def form_invalid(self, form):
        messages.error(
            self.request,
            _('Something went wrong, your changes could not be saved. Please see below for details'),
        )
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse(
            'eventyay_common:organizer.update',
            kwargs={'organizer': self.request.organizer.slug},
        )


class TeamUpdateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, UpdateView):
    model = Team
    template_name = 'eventyay_common/organizers/teams/team_edit.html'
    context_object_name = 'team'
    form_class = TeamForm
    permission = 'can_change_teams'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organizer'] = self.request.organizer
        return kwargs

    def get_object(self, queryset=None):
        self.object = get_object_or_404(Team, organizer=self.request.organizer, pk=self.kwargs.get('team'))
        self.old_name = self.object.name
        return self.object

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['talk_edit_url'] = urljoin(settings.TALK_HOSTNAME, f'orga/organizer/{self.request.organizer.slug}')
        return ctx

    def get_success_url(self):
        return reverse(
            'eventyay_common:organizer.update',
            kwargs={'organizer': self.request.organizer.slug},
        )


    @transaction.atomic
    @scopes_disabled()
    def form_valid(self, form):
        if form.has_changed():
            data = {}

            for field in form.changed_data:
                field_value = getattr(self.object, field)
                if isinstance(self.object._meta.get_field(field), ManyToManyField):
                    data[field] = [obj.id for obj in field_value.all()]
                else:
                    data[field] = field_value

            for field in self.object._meta.many_to_many:
                field_value = getattr(self.object, field.name)
                data[field.name] = [obj.id for obj in field_value.all()]

            self.object.log_action(
                'eventyay.team.changed',
                user=self.request.user,
                data=data,
            )

        team_name = self.object.name
        messages.success(self.request, _(f"Changes to the team '{team_name}' have been saved."))
        form.instance.organizer = self.request.organizer
        response = super().form_valid(form)
        return response

    def form_invalid(self, form):
        messages.error(
            self.request,
            _('Something went wrong, your changes could not be saved.'),
        )
        return super().form_invalid(form)


class TeamDeleteView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DeleteView):
    model = Team
    template_name = 'eventyay_common/organizers/teams/team_delete.html'
    context_object_name = 'team'
    permission = 'can_change_teams'

    def get_object(self, queryset=None):
        return get_object_or_404(Team, organizer=self.request.organizer, pk=self.kwargs.get('team'))

    def get_context_data(self, *args, **kwargs) -> dict:
        context = super().get_context_data(*args, **kwargs)
        context['possible'] = self.can_deleted()
        return context

    def can_deleted(self) -> bool:
        return (
            self.request.organizer.teams.exclude(pk=self.kwargs.get('team'))
            .filter(can_change_teams=True, members__isnull=False)
            .exists()
        )

    @transaction.atomic
    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object = self.get_object()
        if self.can_deleted():
            team_name = self.object.name
            self.object.delete()
            messages.success(self.request, _(f"The team '{team_name}' has been deleted."))
        else:
            messages.error(self.request, _(f"The team '{team_name}' cannot be deleted."))
        
        return redirect(success_url)

    def get_success_url(self):
        return reverse(
            'eventyay_common:organizer.update',
            kwargs={
                'organizer': self.request.organizer.slug,
            },
        )
