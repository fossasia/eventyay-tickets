import logging

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, ListView, TemplateView
from django_context_decorator import context
from django_scopes import scopes_disabled

from eventyay.common.exceptions import SendMailException
from eventyay.common.text.phrases import phrases
from eventyay.common.views import CreateOrUpdateView
from eventyay.common.views.generic import OrgaCRUDView
from eventyay.common.views.mixins import (
    ActionConfirmMixin,
    Filterable,
    PaginationMixin,
    PermissionRequired,
    Sortable,
)
from eventyay.event.forms import OrganizerForm, TeamForm, TeamInviteForm
from eventyay.base.models import Event
from eventyay.base.models.organizer import (
    Organizer,
    Team,
    TeamInvite,
    check_access_permissions,
)
from eventyay.person.forms import UserSpeakerFilterForm
from eventyay.base.models import User

logger = logging.getLogger(__name__)


class TeamView(OrgaCRUDView):
    model = Team
    form_class = TeamForm
    template_namespace = "orga/organizer"
    url_name = "organizer.teams"
    context_object_name = "team"
    permission_required = "event.update_team"

    def get_queryset(self):
        return self.request.organizer.teams.all().order_by("-all_events", "-id")

    def get_permission_required(self):
        return self.permission_required

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organizer"] = self.request.organizer
        return kwargs

    def get_success_url(self):
        if self.invite_form:
            return self.reverse("update", instance=self.object)
        return self.reverse("list")

    def get_generic_permission_object(self):
        return self.request.organizer

    def get_generic_title(self, instance=None):
        if instance:
            return (
                _("Team")
                + f" {phrases.base.quotation_open}{instance.name}{phrases.base.quotation_close}"
            )
        if self.action == "create":
            return _("New team")
        return _("Teams")

    @context
    @cached_property
    def invite_form(self):
        if self.action not in ("update", "detail") or not self.object:
            return None
        is_bound = (
            self.request.method == "POST" and self.request.POST.get("form") == "invite"
        )
        return TeamInviteForm(self.request.POST if is_bound else None, prefix="invite")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.action == "update":
            context["invite_form"] = self.invite_form
            context["members"] = self.object.members.all().order_by("fullname")
            context["invites"] = self.object.invites.all()
        return context

    def invite_form_handler(self, request):
        if self.invite_form.is_valid():
            invites = self.invite_form.save(team=self.object)
            if len(invites) == 1:
                messages.success(self.request, _("The invitation has been sent."))
            else:
                messages.success(self.request, _("The invitations have been sent."))
            return redirect(self.request.path)
        for error in self.invite_form.errors.values():
            messages.error(self.request, "\n".join(error))
        return self.form_invalid(self.get_form(instance=self.object))

    def form_handler(self, request, *args, **kwargs):
        if self.action == "update" and request.POST.get("form") == "invite":
            return self.invite_form_handler(request)
        return super().form_handler(request, *args, **kwargs)

    def form_valid(self, form):
        if self.action == "create":
            return super().form_valid(form)
        warnings = []
        try:
            with transaction.atomic():
                form.instance.organizer = self.request.organizer
                result = super().form_valid(form)
                warnings = check_access_permissions(self.request.organizer)
        except Exception as exc:
            messages.error(self.request, str(exc))
            return self.form_invalid(form)
        if warnings:
            for warning in warnings:
                messages.warning(self.request, warning)
        return result

    def perform_delete(self):
        warnings = []
        with transaction.atomic():
            self.object.log_action(
                "eventyay.team.delete", person=self.request.user, orga=True
            )
            self.object.invites.all().delete()
            self.object.delete()
            warnings = check_access_permissions(self.request.organizer)
            messages.success(self.request, _("The team was removed."))

        if warnings:
            for warning in warnings:
                messages.warning(self.request, warning)
        return True

    @transaction.atomic
    def delete_handler(self, request, *args, **kwargs):
        """POST handler for delete view"""
        try:
            return super().delete_handler(request, *args, **kwargs)
        except Exception as exc:
            messages.error(self.request, str(exc))
        return self.update(request, *args, **kwargs)


class InviteMixin(PermissionRequired):
    permission_required = "event.update_team"
    model = TeamInvite

    def get_permission_object(self):
        return self.request.organizer

    @cached_property
    def invite(self):
        return self.get_object()

    def get_object(self):
        return get_object_or_404(
            TeamInvite.objects.filter(
                team__organizer=self.request.organizer, team__pk=self.kwargs["pk"]
            ),
            pk=self.kwargs["invite_pk"],
        )

    @cached_property
    def team(self):
        return self.invite.team


class TeamUninvite(InviteMixin, ActionConfirmMixin, DetailView):
    action_title = _("Retract invitation")
    action_text = _("Are you sure you want to retract the invitation to this user?")

    def action_object_name(self):
        return self.invite.email

    @property
    def action_back_url(self):
        return self.team.orga_urls.base

    def post(self, request, *args, **kwargs):
        team = self.team
        email = self.invite.email
        self.invite.delete()
        team.log_action(
            "eventyay.team.invite.orga.retract",
            person=self.request.user,
            orga=True,
            data={"email": email},
        )
        messages.success(request, _("The team invitation was retracted."))
        return redirect(team.orga_urls.base)


class TeamResend(InviteMixin, ActionConfirmMixin, DetailView):
    action_title = _("Resend invite")
    action_text = _("Are you sure you want to resend the invitation to this user?")
    action_confirm_color = "success"
    action_confirm_icon = "envelope"
    action_confirm_label = phrases.base.send

    def action_object_name(self):
        return self.invite.email

    @property
    def action_back_url(self):
        return self.team.orga_urls.base

    def post(self, request, *args, **kwargs):
        self.invite.send()
        messages.success(request, _("The team invitation was sent again."))
        return redirect(self.team.orga_urls.base)


class TeamMemberMixin(PermissionRequired):
    permission_required = "event.update_team"

    def get_permission_object(self):
        return self.request.organizer

    @cached_property
    def team(self):
        return get_object_or_404(
            self.request.organizer.teams.all(), pk=self.kwargs["team_pk"]
        )

    def get_object(self, queryset=None):
        return get_object_or_404(self.team.members.all(), pk=self.kwargs["user_pk"])

    @context
    @cached_property
    def member(self):
        return self.get_object()

    @property
    def action_back_url(self):
        return self.team.orga_urls.base

    def action_object_name(self):
        return f"{self.member.get_display_name()} ({self.member.email})"


class TeamMemberDelete(TeamMemberMixin, ActionConfirmMixin, DetailView):

    def post(self, request, *args, **kwargs):
        warnings = []
        try:
            with transaction.atomic():
                self.team.remove_member(self.member)
                self.team.log_action(
                    "eventyay.team.remove_member",
                    person=self.request.user,
                    orga=True,
                    data={
                        "id": self.member.pk,
                        "name": self.member.fullname,
                        "email": self.member.email,
                    },
                )
                warnings = check_access_permissions(self.request.organizer)
                messages.success(request, _("The member was removed from the team."))
        except Exception as e:
            messages.error(request, str(e))
            return redirect(self.action_back_url)

        if warnings:
            for warning in warnings:
                messages.warning(request, warning)
        return redirect(self.action_back_url)


class TeamResetPassword(TeamMemberMixin, ActionConfirmMixin, TemplateView):
    action_confirm_icon = "key"
    action_confirm_label = phrases.base.password_reset_heading
    action_title = phrases.base.password_reset_heading
    action_text = _(
        "Do your really want to reset this user’s password? They won’t be able to log in until they set a new password."
    )

    def post(self, request, *args, **kwargs):
        user_to_reset = self.member
        try:
            user_to_reset.reset_password(event=None, user=self.request.user)
            messages.success(self.request, phrases.orga.password_reset_success)
        except SendMailException:  # pragma: no cover
            messages.error(self.request, phrases.orga.password_reset_fail)
        return redirect(self.action_back_url)


class OrganizerDetail(PermissionRequired, CreateOrUpdateView):
    template_name = "orga/organizer/detail.html"
    model = Organizer
    permission_required = "event.update_organizer"
    form_class = OrganizerForm

    def get_object(self, queryset=None):
        return getattr(self.request, "organizer", None)

    @cached_property
    def object(self):
        return self.get_object()

    def get_permission_object(self):
        return self.object

    def form_valid(self, form):
        result = super().form_valid(form)
        if form.has_changed():
            messages.success(self.request, phrases.base.saved)
        return result

    def get_success_url(self):
        return self.request.path


class OrganizerDelete(PermissionRequired, ActionConfirmMixin, DetailView):
    permission_required = "person.administrator_user"
    model = Organizer
    action_text = (
        _(
            "ALL related data for ALL events, such as proposals, and speaker profiles, and uploads, "
            "will also be deleted and cannot be restored."
        )
        + " "
        + phrases.base.delete_warning
    )

    def get_object(self, queryset=None):
        return self.request.organizer

    def get_permission_object(self, queryset=None):
        return self.request.user

    def action_object_name(self):
        return _("Organizer") + f": {self.get_object().name}"

    @property
    def action_back_url(self):
        return self.get_object().orga_urls.settings

    def post(self, *args, **kwargs):
        organizer = self.get_object()
        organizer.shred(person=self.request.user)
        messages.success(
            self.request, _("The organizer and all related data have been deleted.")
        )
        return HttpResponseRedirect(reverse("orga:event.list"))


def get_speaker_access_events_for_user(*, user, organizer):
    events = set()
    no_access_events = set()
    # Use prefetch_related for efficiency if called often
    teams = user.teams.filter(organizer=organizer).prefetch_related(
        "limit_events", "limit_tracks"
    )
    for team in teams:
        if team.can_change_submissions:
            if team.all_events:
                # This user has access to all speakers for all events,
                # so we can cut our logic short here.
                return organizer.events.all()
            else:
                events.update(team.limit_events.values_list("pk", flat=True))
        elif team.is_reviewer and not team.limit_tracks.exists():
            # Reviewers *can* have access to speakers, but they do not necessarily
            # do, so we need to check permissions for each event. We do skip teams
            # that are limited to specific tracks.
            team_events = None
            if team.all_events:
                team_events = organizer.events.all()
            else:
                team_events = team.limit_events.all()
            if team_events:
                for event in team_events:
                    if event.pk in events or event.pk in no_access_events:
                        continue
                    if user.has_perm("person.orga_list_speakerprofile", event):
                        events.add(event.pk)
                    else:
                        no_access_events.add(event.pk)
    return Event.objects.filter(pk__in=list(events))


@method_decorator(scopes_disabled(), "dispatch")
class OrganizerSpeakerList(
    PermissionRequired, Sortable, Filterable, PaginationMixin, ListView
):
    template_name = "orga/organizer/speaker_list.html"
    permission_required = "event.view_organizer"
    context_object_name = "speakers"
    default_filters = ("email__icontains", "fullname__icontains")
    sortable_fields = ("email", "fullname", "accepted_submission_count", "submission_count")
    default_sort_field = "fullname"

    def get_permission_object(self):
        return self.request.organizer

    def get_filter_form(self):
        return UserSpeakerFilterForm(self.request.GET, events=self.events)

    @context
    @cached_property
    def events(self):
        return get_speaker_access_events_for_user(
            user=self.request.user, organizer=self.request.organizer
        )

    def get_queryset(self):
        qs = self.filter_queryset(User.objects.all())
        return self.sort_queryset(qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[self.context_object_name] = list(context[self.context_object_name])
        return context


def speaker_search(request, *args, **kwargs):
    search = request.GET.get("search")
    if not search or len(search) < 3:
        return JsonResponse({"count": 0, "results": []})

    with scopes_disabled():
        events = get_speaker_access_events_for_user(
            user=request.user, organizer=request.organizer
        )
        users = (
            User.objects.filter(profiles__event__in=events)
            .filter(Q(fullname__icontains=search) | Q(email__icontains=search))
            .distinct()[:8]
        )
        users = list(users)

    return JsonResponse(
        {
            "count": len(users),
            "results": [{"email": user.email, "name": user.fullname} for user in users],
        }
    )
