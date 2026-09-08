import logging
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, ManyToManyField
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView
from django_scopes import scopes_disabled

from eventyay.base.auth import get_auth_backends
from eventyay.base.models import Organizer, Team
from eventyay.base.models.auth import User
from eventyay.base.models.organizer import TeamAPIToken, TeamInvite
from eventyay.base.services.mail import SendMailException, mail
from eventyay.base.services.teams import send_team_invitation_email
from eventyay.control.forms.filter import OrganizerFilterForm
from eventyay.control.permissions import (
    OrganizerCreationPermissionMixin,
    OrganizerPermissionRequiredMixin,
)
from eventyay.control.views import CreateView, PaginationMixin, UpdateView
from eventyay.control.views.organizer import InviteForm, TokenForm
from eventyay.helpers.urls import build_absolute_uri as build_global_uri

from ...control.forms.organizer_forms import OrganizerForm, OrganizerUpdateForm, TeamForm
from ..video.traits_sync import sync_video_traits_for_team


logger = logging.getLogger(__name__)


class OrganizerList(OrganizerCreationPermissionMixin, PaginationMixin, ListView):
    model = Organizer
    context_object_name = 'organizers'
    template_name = 'eventyay_common/organizers/index.html'

    def get_queryset(self):
        qs = Organizer.objects.all()
        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)
        if not self.request.user.has_active_staff_session(self.request.session.session_key):
            qs = qs.filter(pk__in=self.request.user.teams.values_list('organizer', flat=True))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        ctx['can_create_organizer'] = self._can_create_organizer(self.request.user)
        ctx['default_organizer'] = (
            self.request.user.get_default_organizer() if self.request.user.is_authenticated else None
        )
        return ctx

    @cached_property
    def filter_form(self):
        return OrganizerFilterForm(data=self.request.GET, request=self.request)


class OrganizerCreate(OrganizerCreationPermissionMixin, CreateView):
    model = Organizer
    form_class = OrganizerForm
    template_name = 'eventyay_common/organizers/create.html'
    context_object_name = 'organizer'

    def dispatch(self, request, *args, **kwargs):
        # Check if user has permission to create organizers
        if not self._can_create_organizer(request.user):
            raise PermissionDenied(_('You do not have permission to create organizers. Please contact an administrator.'))
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['request'] = self.request
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, _('New organizer is created.'))
        had_default = bool(self.request.user.get_default_organizer())
        response = super().form_valid(form)
        team = Team.objects.create(
            organizer=form.instance,
            name=_('Core Organizing Team'),
            all_events=True,
            can_create_events=True,
            can_change_teams=True,
            can_manage_gift_cards=True,
            can_change_organizer_settings=True,
            can_change_event_settings=True,
            can_change_config=True,
            can_change_items=True,
            can_view_orders=True,
            can_change_orders=True,
            can_manage_bank_transfers=True,
            can_checkin_orders=True,
            can_view_vouchers=True,
            can_change_vouchers=True,
            can_change_submissions=True,
            is_reviewer=True,
            can_change_exhibition_proposals=True,
            is_exhibition_reviewer=True,
            can_manage_social_media=True,
            can_video_manage_content=True,
            can_video_moderate=True,
            can_video_manage_kiosks=True,
            can_video_view_analytics=True,
        )
        # Trigger webhook in talk to create organiser in talk component
        team.members.add(self.request.user)
        if form.cleaned_data.get('set_as_default') or not had_default:
            self.request.user.default_organizer = self.object
            self.request.user.save(update_fields=['default_organizer'])
        return response

    def get_success_url(self) -> str:
        return reverse('eventyay_common:organizers')

class OrganizerTeamsView(UpdateView, OrganizerPermissionRequiredMixin):
    model = Organizer
    form_class = OrganizerUpdateForm
    template_name = 'eventyay_common/organizers/edit.html'
    permission = 'can_change_organizer_settings'
    context_object_name = 'organizer'

    def dispatch(self, request, *args, **kwargs):
        self._team_form_overrides = {}
        self._team_create_form_override = None
        self._forced_section = None
        self._selected_team_override = None
        self._selected_panel_override = None
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def object(self) -> Organizer:
        return self.request.organizer

    def get_object(self, queryset=None) -> Organizer:
        return self.object

    @cached_property
    def can_edit_general_info(self) -> bool:
        return self.request.user.has_organizer_permission(
            self.request.organizer,
            'can_change_organizer_settings',
            request=self.request,
        )

    @cached_property
    def can_manage_teams(self) -> bool:
        return self.request.user.has_organizer_permission(
            self.request.organizer,
            'can_change_teams',
            request=self.request,
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if action := request.POST.get('team_action'):
            if not self.can_manage_teams:
                raise PermissionDenied()
            handlers = {
                'create': self._handle_team_create,
                'update': self._handle_team_update,
                'members': self._handle_team_members,
                'tokens': self._handle_team_tokens,
            }
            handler = handlers.get(action)
            if handler:
                return handler()
        return super().post(request, *args, **kwargs)

    def _validated_teams_return_next(self, candidate: str | None) -> str | None:
        if candidate and url_has_allowed_host_and_scheme(
            candidate,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return candidate
        return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['can_manage_teams'] = self.can_manage_teams
        ctx['active_section'] = 'teams'
        ctx['teams_return_next'] = self._validated_teams_return_next(self.request.GET.get('next'))
        selected_team_id = self._selected_team_override or self.request.GET.get('team')
        selected_panel = self._selected_panel_override or self.request.GET.get('panel')
        if selected_team_id and not selected_panel:
            selected_panel = 'permissions'
        ctx['selected_team_id'] = selected_team_id
        ctx['selected_panel'] = selected_panel

        if self.can_manage_teams:
            teams_qs = self._get_team_queryset()
            ctx['team_create_form'] = self._get_team_create_form()
            # Iterate within scopes_disabled to avoid scope errors when accessing related objects
            with scopes_disabled():
                ctx['teams'] = list(teams_qs)
                ctx['team_panels'] = [
                    self._build_team_panel(team, selected_team_id, selected_panel) for team in ctx['teams']
                ]
        else:
            ctx['teams'] = []
            ctx['team_panels'] = []
            ctx['team_create_form'] = None

        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if not self.can_edit_general_info:
            form.fields['name'].disabled = True
            form.fields['slug'].disabled = True
        return form

    @transaction.atomic
    def form_valid(self, form):
        if not self.can_edit_general_info:
            form.cleaned_data['name'] = self.object.name
            form.cleaned_data['slug'] = self.object.slug

        if 'set_as_default' in form.cleaned_data:
            if form.cleaned_data['set_as_default']:
                if self.request.user.teams.filter(organizer=self.object).exists():
                    self.request.user.default_organizer = self.object
                    self.request.user.save(update_fields=['default_organizer'])
            else:
                if self.request.user.default_organizer_id == self.object.id:
                    self.request.user.default_organizer = None
                    self.request.user.save(update_fields=['default_organizer'])

        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse('eventyay_common:organizers')

    def _get_team_queryset(self):
        if not hasattr(self, '_team_queryset'):
            with scopes_disabled():
                self._team_queryset = (
                    self.request.organizer.teams.annotate(
                        memcount=Count('members', distinct=True),
                        eventcount=Count('limit_events', distinct=True),
                        invcount=Count('invites', distinct=True),
                    )
                    .prefetch_related('members', 'invites', 'tokens', 'limit_events')
                    .order_by('name')
                )
        return self._team_queryset

    def _get_team_create_form(self):
        if self._team_create_form_override is not None:
            return self._team_create_form_override
        with scopes_disabled():
            return TeamForm(prefix='team-create', organizer=self.request.organizer)

    def _build_team_panel(self, team, selected_team_id, selected_panel):
        is_selected_team = str(team.pk) == str(selected_team_id) if selected_team_id else False
        open_panel = selected_panel if is_selected_team else None
        open_permissions = open_panel in (None, 'permissions') and is_selected_team
        open_members = open_panel == 'members'

        override = self._team_form_overrides.get(team.pk, {})
        form = override.get('form')
        if form is None:
            with scopes_disabled():
                form = TeamForm(
                    prefix=self._team_form_prefix(team),
                    organizer=self.request.organizer,
                    instance=team,
                )
        invite_form = override.get('invite_form') or InviteForm(
            prefix=self._invite_form_prefix(team),
        )
        token_form = override.get('token_form') or TokenForm(
            prefix=self._token_form_prefix(team),
        )

        return {
            'team': team,
            'form': form,
            'invite_form': invite_form,
            'token_form': token_form,
            'members': team.members.all(),
            'invites': team.invites.all(),
            'tokens': team.active_tokens,
            'can_delete': self._can_delete_team(team),
            'is_permissions_open': open_permissions,
            'is_members_open': open_members,
        }

    def _team_form_prefix(self, team: Team) -> str:
        return f'team-{team.pk}'

    def _invite_form_prefix(self, team: Team) -> str:
        return f'{self._team_form_prefix(team)}-invite'

    def _token_form_prefix(self, team: Team) -> str:
        return f'{self._team_form_prefix(team)}-token'

    def _set_panel_override(self, team_id, panel_key):
        self._selected_team_override = str(team_id)
        self._selected_panel_override = panel_key

    def _set_team_override(self, team_id, *, form=None, invite_form=None, token_form=None):
        override = self._team_form_overrides.setdefault(team_id, {})
        if form is not None:
            override['form'] = form
        if invite_form is not None:
            override['invite_form'] = invite_form
        if token_form is not None:
            override['token_form'] = token_form

    def _teams_tab_url(self, team_id=None, section='teams', panel=None, anchor='organizer-messages'):
        base = reverse('eventyay_common:organizer.teams', kwargs={'organizer': self.request.organizer.slug})
        query = {'section': section}
        if team_id:
            query['team'] = team_id
        if panel:
            query['panel'] = panel
        url = f'{base}?{urlencode(query)}'
        if anchor:
            url = f'{url}#{anchor}'
        return url

    def _build_unbound_organizer_form(self):
        form_class = self.get_form_class()
        kwargs = self.get_form_kwargs()
        kwargs.pop('data', None)
        kwargs.pop('files', None)
        return form_class(**kwargs)

    def _render_with_team_errors(self, section='teams'):
        self._forced_section = section
        form = self._build_unbound_organizer_form()
        return self.render_to_response(self.get_context_data(form=form))

    def _get_team_from_post(self):
        return get_object_or_404(
            Team,
            organizer=self.request.organizer,
            pk=self.request.POST.get('team_id'),
        )

    def _redirect_to_team_members_panel(self, team_id):
        """Helper to redirect to team members panel with error state."""
        self._set_panel_override(team_id, 'members')
        return redirect(self._teams_tab_url(team_id, section='permissions', panel='members'))

    def _redirect_to_team_permissions(self, team_id):
        """Helper to redirect to team permissions section."""
        return redirect(self._teams_tab_url(team_id, section='permissions'))

    def _render_members_error(self, team_id, invite_form=None):
        """Helper to render team members section with errors."""
        self._set_panel_override(team_id, 'members')
        if invite_form is not None:
            self._set_team_override(team_id, invite_form=invite_form)
        return self._render_with_team_errors('permissions')

    def _handle_team_create(self):
        with scopes_disabled():
            form = TeamForm(
                data=self.request.POST,
                organizer=self.request.organizer,
                prefix='team-create',
            )
        if form.is_valid():
            with transaction.atomic():
                with scopes_disabled():
                    team = form.save(commit=False)
                    team.organizer = self.request.organizer
                    team.save()
                    form.save_m2m()
                team.members.add(self.request.user)
                team.log_action(
                    'eventyay.team.created',
                    user=self.request.user,
                    data=self._build_changed_data_dict(form, team),
                )
            messages.success(
                self.request,
                _('The team has been created. You can now add members to the team.'),
            )
            return redirect(self._teams_tab_url(team.pk, anchor=None))

        messages.error(
            self.request,
            _('Something went wrong, your changes could not be saved. Please see below for details.'),
        )
        self._team_create_form_override = form
        return self._render_with_team_errors()

    def _handle_team_update(self):
        team = self._get_team_from_post()
        with scopes_disabled():
            form = TeamForm(
                data=self.request.POST,
                organizer=self.request.organizer,
                instance=team,
                prefix=self._team_form_prefix(team),
            )
        self._forced_section = 'permissions'

        if form.is_valid():
            with transaction.atomic():
                with scopes_disabled():
                    form.instance.organizer = self.request.organizer
                    form.save()
            if form.has_changed():
                team.log_action(
                    'eventyay.team.changed',
                    user=self.request.user,
                    data=self._collect_team_change_data(team, form),
                )
            team_name = team.name
            messages.success(
                self.request,
                _("Changes to the team '%(team_name)s' have been saved.") % {'team_name': team_name},
            )
            sync_video_traits_for_team(team)
            return_next = self._validated_teams_return_next(self.request.POST.get('next'))
            if return_next:
                return redirect(return_next)
            return redirect(self._teams_tab_url(team.pk, section='permissions'))

        messages.error(
            self.request,
            _('Something went wrong, your changes could not be saved.'),
        )
        self._set_panel_override(team.pk, 'permissions')
        self._set_team_override(team.pk, form=form)
        return self._render_with_team_errors('permissions')

    def _handle_team_members(self):
        team = self._get_team_from_post()
        self._forced_section = 'permissions'
        invite_form_prefix = self._invite_form_prefix(team)
        prefixed_user_field = f'{invite_form_prefix}-user'
        invite_form = InviteForm(
            data=(self.request.POST if prefixed_user_field in self.request.POST else None),
            prefix=invite_form_prefix,
        )

        post = self.request.POST

        with transaction.atomic():
            if 'remove-member' in post:
                return self._handle_remove_member(team, post)
            elif 'remove-invite' in post:
                return self._handle_remove_invite(team, post)
            elif 'resend-invite' in post:
                return self._handle_resend_invite(team, post)
            elif f'{invite_form_prefix}-user' in post and invite_form.is_valid() and invite_form.has_changed():
                return self._handle_add_member_or_invite(team, invite_form, post)

        messages.error(self.request, _('Your changes could not be saved.'))
        return self._render_members_error(team.pk, invite_form)

    def _handle_remove_member(self, team, post):
        """Handle removing a member from the team."""
        try:
            user = User.objects.get(pk=post.get('remove-member'))
        except (User.DoesNotExist, ValueError):
            return self._redirect_to_team_permissions(team.pk)

        other_admin_teams = (
            self.request.organizer.teams.exclude(pk=team.pk)
            .filter(can_change_teams=True, members__isnull=False)
            .exists()
        )
        if not other_admin_teams and team.can_change_teams and team.members.count() == 1:
            messages.error(
                self.request,
                _(
                    'You cannot remove the last member from this team as no one would '
                    'be left with the permission to change teams.'
                ),
            )
            return self._redirect_to_team_members_panel(team.pk)

        team.members.remove(user)
        team.log_action(
            'eventyay.team.member.removed',
            user=self.request.user,
            data={'email': user.email, 'user': user.pk},
        )
        sync_video_traits_for_team(team, members=[user])
        messages.success(self.request, _('The member has been removed from the team.'))
        return self._redirect_to_team_permissions(team.pk)

    def _handle_remove_invite(self, team, post):
        """Handle removing an invite."""
        try:
            invite = team.invites.get(pk=post.get('remove-invite'))
        except (TeamInvite.DoesNotExist, ValueError):
            messages.error(self.request, _('Invalid invite selected.'))
            return self._redirect_to_team_members_panel(team.pk)

        invite.delete()
        team.log_action(
            'eventyay.team.invite.deleted',
            user=self.request.user,
            data={'email': invite.email},
        )
        messages.success(self.request, _('The invite has been revoked.'))
        return self._redirect_to_team_permissions(team.pk)

    def _handle_resend_invite(self, team, post):
        """Handle resending an invite."""
        try:
            invite = team.invites.get(pk=post.get('resend-invite'))
        except (TeamInvite.DoesNotExist, ValueError):
            messages.error(self.request, _('Invalid invite selected.'))
            return self._redirect_to_team_members_panel(team.pk)

        self._send_invite(invite)
        team.log_action(
            'eventyay.team.invite.resent',
            user=self.request.user,
            data={'email': invite.email},
        )
        messages.success(self.request, _('The invite has been resent.'))
        return self._redirect_to_team_permissions(team.pk)

    def _handle_add_member_or_invite(self, team, invite_form, post):
        """Handle adding a member or creating an invite."""
        try:
            user = User.objects.get(email__iexact=invite_form.cleaned_data['user'])
        except User.DoesNotExist:
            return self._handle_create_invite(team, invite_form)

        if team.members.filter(pk=user.pk).exists():
            messages.error(
                self.request,
                _('This user already has permissions for this team.'),
            )
            return self._render_members_error(team.pk, invite_form)

        team.members.add(user)

        team.log_action(
            'eventyay.team.member.added',
            user=self.request.user,
            data={'email': user.email, 'user': user.pk},
        )
        sync_video_traits_for_team(team, members=[user])

        send_team_invitation_email(
            user=user,
            organizer_name=self.request.organizer.name,
            team_name=team.name,
            url=build_global_uri(
                'eventyay_common:organizer.team',
                kwargs={
                    'organizer': self.request.organizer.slug,
                    'team': team.pk,
                },
            ),
            locale=self.request.LANGUAGE_CODE,
            is_registered_user=True,
        )

        messages.success(self.request, _('The new member has been added to the team.'))
        return self._redirect_to_team_members_panel(team.pk)

    def _handle_create_invite(self, team, invite_form):
        """Handle creating an invite for a user that doesn't exist yet."""
        if team.invites.filter(email__iexact=invite_form.cleaned_data['user']).exists():
            messages.error(
                self.request,
                _('This user already has been invited for this team.'),
            )
            return self._render_members_error(team.pk, invite_form)

        if 'native' not in get_auth_backends():
            messages.error(
                self.request,
                _('Users need to have a eventyay account before they can be invited.'),
            )
            return self._render_members_error(team.pk, invite_form)

        invite = team.invites.create(email=invite_form.cleaned_data['user'])
        self._send_invite(invite)
        team.log_action(
            'eventyay.team.invite.created',
            user=self.request.user,
            data={'email': invite_form.cleaned_data['user']},
        )
        messages.success(self.request, _('The new member has been invited to the team.'))
        return self._redirect_to_team_members_panel(team.pk)

    def _handle_team_tokens(self):
        team = self._get_team_from_post()
        self._forced_section = 'permissions'
        token_form_prefix = self._token_form_prefix(team)
        prefixed_name_field = f'{token_form_prefix}-name'
        token_form = TokenForm(
            data=(self.request.POST if prefixed_name_field in self.request.POST else None),
            prefix=token_form_prefix,
        )

        post = self.request.POST

        with transaction.atomic():
            if 'remove-token' in post:
                return self._handle_remove_token(team, post)
            if prefixed_name_field in post and token_form.is_valid() and token_form.has_changed():
                return self._handle_create_token(team, token_form)

        messages.error(self.request, _('Your changes could not be saved.'))
        self._set_panel_override(team.pk, 'members')
        self._set_team_override(team.pk, token_form=token_form)
        return self._render_with_team_errors('permissions')

    def _handle_remove_token(self, team, post):
        """Handle removing a token."""
        try:
            token = team.tokens.get(pk=post.get('remove-token'))
        except (TeamAPIToken.DoesNotExist, ValueError):
            messages.error(self.request, _('Invalid token selected.'))
            return self._redirect_to_team_members_panel(team.pk)

        token.active = False
        token.save()
        team.log_action(
            'eventyay.team.token.deleted',
            user=self.request.user,
            data={'name': token.name},
        )
        messages.success(self.request, _('The token has been revoked.'))
        return self._redirect_to_team_permissions(team.pk)

    def _handle_create_token(self, team, token_form):
        """Handle creating a new token."""
        token = team.tokens.create(name=token_form.cleaned_data['name'])
        team.log_action(
            'eventyay.team.token.created',
            user=self.request.user,
            data={'name': token_form.cleaned_data['name'], 'id': token.pk},
        )
        messages.success(
            self.request,
            _(
                'A new API token has been created with the following secret: {}\n'
                'Please copy this secret to a safe place. You will not be able to '
                'view it again here.'
            ).format(token.token),
        )
        return self._redirect_to_team_permissions(team.pk)

    def _send_invite(self, instance):
        try:
            mail(
                instance.email,
                _('eventyay account invitation'),
                'pretixcontrol/email/invitation.txt',
                {
                    'user': self.request.user,
                    'organizer': self.request.organizer.name,
                    'team': instance.team.name,
                    'url': build_global_uri('eventyay_common:auth.invite', kwargs={'token': instance.token}),
                },
                event=None,
                locale=self.request.LANGUAGE_CODE,
            )
        except SendMailException as e:
            logger.warning(
                "Failed to send invitation email to %s for team '%s': %s",
                instance.email,
                instance.team.name,
                str(e),
            )

    def _can_delete_team(self, team: Team) -> bool:
        return (
            self.request.organizer.teams.exclude(pk=team.pk)
            .filter(can_change_teams=True, members__isnull=False)
            .exists()
        )

    def _build_changed_data_dict(self, form, obj):
        data = {}
        model = form._meta.model
        with scopes_disabled():
            for field_name in form.changed_data:
                model_field = model._meta.get_field(field_name)
                field_value = getattr(obj, field_name)
                if isinstance(model_field, ManyToManyField):
                    data[field_name] = [instance.id for instance in field_value.all()]
                else:
                    data[field_name] = field_value
        return data

    def _collect_team_change_data(self, team: Team, form: TeamForm):
        """Collect only changed field data for audit logging.
        
        Args:
            team: The Team model instance
            form: The TeamForm with changed_data populated
            
        Returns:
            dict: Dictionary of changed field names to their new values
        """
        data = {}
        model = form._meta.model
        with scopes_disabled():
            for field_name in form.changed_data:
                model_field = model._meta.get_field(field_name)
                field_value = getattr(team, field_name)
                if isinstance(model_field, ManyToManyField):
                    data[field_name] = [instance.id for instance in field_value.all()]
                else:
                    data[field_name] = field_value
        return data
