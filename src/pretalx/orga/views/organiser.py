import logging

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, ListView, TemplateView
from django_context_decorator import context
from django_scopes import scopes_disabled

from pretalx.common.exceptions import SendMailException
from pretalx.common.text.phrases import phrases
from pretalx.common.views import CreateOrUpdateView
from pretalx.common.views.mixins import (
    ActionConfirmMixin,
    Filterable,
    PaginationMixin,
    PermissionRequired,
    Sortable,
)
from pretalx.event.forms import OrganiserForm, TeamForm, TeamInviteForm
from pretalx.event.models import Event
from pretalx.event.models.organiser import (
    Organiser,
    Team,
    TeamInvite,
    check_access_permissions,
)
from pretalx.person.forms import UserSpeakerFilterForm
from pretalx.person.models import User
from pretalx.submission.models.submission import SubmissionStates

logger = logging.getLogger(__name__)


class TeamMixin:
    def _get_team(self):
        if "pk" in getattr(self, "kwargs", {}):
            return get_object_or_404(
                self.request.organiser.teams.all(), pk=self.kwargs["pk"]
            )

    def get_object(self, queryset=None):
        return self._get_team()

    @context
    @cached_property
    def team(self):
        return self._get_team()

    @cached_property
    def object(self):
        return self.get_object()


class TeamDetail(PermissionRequired, TeamMixin, CreateOrUpdateView):
    permission_required = "orga.change_teams"
    template_name = "orga/settings/team_detail.html"
    form_class = TeamForm
    model = Team

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organiser"] = self.request.organiser
        return kwargs

    def get_object(self, queryset=None):
        if "pk" not in self.kwargs:
            return None
        return super().get_object(queryset=queryset)

    def get_permission_object(self):
        if "pk" not in self.kwargs:
            return self.request.organiser
        return self.get_object()

    @context
    @cached_property
    def invite_form(self):
        is_bound = (
            self.request.method == "POST" and self.request.POST.get("form") == "invite"
        )
        return TeamInviteForm(self.request.POST if is_bound else None, prefix="invite")

    @context
    @cached_property
    def members(self):
        if not self.team or not self.team.pk:
            return []
        return self.team.members.all().order_by("name")

    def post(self, *args, **kwargs):
        if self.invite_form.is_bound:
            if self.invite_form.is_valid():
                invites = self.invite_form.save(team=self.team)
                if len(invites) == 1:
                    messages.success(self.request, _("The invitation has been sent."))
                else:
                    messages.success(self.request, _("The invitations have been sent."))
            else:
                for error in self.invite_form.errors.values():
                    messages.error(self.request, "\n".join(error))
            return redirect(self.request.path)
        return super().post(*args, **kwargs)

    def form_valid(self, form):
        created = not bool(form.instance.pk)
        warnings = []
        try:
            with transaction.atomic():
                form.save()
                if not created:
                    warnings = check_access_permissions(self.request.organiser)
        except Exception as e:
            # We can't save because we would break the organiser's permissions,
            # e.g. leave an event or the entire organiser orphaned.
            messages.error(self.request, str(e))
            return self.get(self.request, *self.args, **self.kwargs)
        if warnings:
            for warning in warnings:
                messages.warning(self.request, warning)
        if created:
            messages.success(self.request, _("The team has been created."))
        elif form.has_changed():
            messages.success(self.request, phrases.base.saved)
        return super().form_valid(form)

    def get_success_url(self):
        if "pk" not in self.kwargs:
            return self.request.organiser.orga_urls.base
        return self.request.GET.get("next", self.request.path)


class TeamDelete(PermissionRequired, TeamMixin, ActionConfirmMixin, DetailView):
    permission_required = "orga.change_teams"

    def get_permission_object(self):
        return self._get_team()

    def get_object(self, queryset=None):
        team = super().get_object()
        if "user_pk" in self.kwargs:
            return team.members.filter(pk=self.kwargs.get("user_pk")).first()
        return team

    def action_object_name(self):
        if "user_pk" in self.kwargs:
            return _("Team member") + f": {self.get_object().name}"
        return _("Team") + f": {self.get_object().name}"

    @property
    def action_back_url(self):
        return self._get_team().orga_urls.base

    @context
    @cached_property
    def member(self):
        member = self.get_object()
        return member if member != self.team else None

    def post(self, request, *args, **kwargs):
        warnings = []
        try:
            with transaction.atomic():
                if "user_pk" in self.kwargs:
                    self.team.members.remove(self.get_object())
                    warnings = check_access_permissions(self.request.organiser)
                    messages.success(
                        request, _("The member was removed from the team.")
                    )
                else:
                    self.get_object().delete()
                    warnings = check_access_permissions(self.request.organiser)
                    messages.success(request, _("The team was removed."))
        except Exception as e:
            messages.error(request, str(e))
            return self.get(request, *args, **kwargs)
        if warnings:
            for warning in warnings:
                messages.warning(request, warning)
        return redirect(self.request.organiser.orga_urls.base)


class InviteMixin:
    def get_permission_object(self):
        return self.request.organiser

    @context
    @cached_property
    def team(self):
        return get_object_or_404(
            self.request.organiser.teams.all(), pk=self.object.team.pk
        )

    @cached_property
    def object(self):
        return get_object_or_404(
            self.team.invites.all(),
            pk=self.kwargs["pk"],
        )


class TeamUninvite(InviteMixin, PermissionRequired, ActionConfirmMixin, DetailView):
    model = TeamInvite
    permission_required = "orga.change_teams"
    action_title = _("Retract invitation")
    action_text = _("Are you sure you want to retract the invitation to this user?")

    def action_object_name(self):
        return self.get_object().email

    @property
    def action_back_url(self):
        return self.get_object().team.orga_urls.base

    def post(self, request, *args, **kwargs):
        self.get_object().delete()
        messages.success(request, _("The team invitation was retracted."))
        return redirect(self.request.organiser.orga_urls.base)


class TeamResend(InviteMixin, PermissionRequired, ActionConfirmMixin, DetailView):
    model = TeamInvite
    permission_required = "orga.change_teams"
    action_title = _("Resend invitation")
    action_text = _("Are you sure you want to resend the invitation to this user?")
    action_confirm_color = "success"
    action_confirm_icon = "envelope"
    action_confirm_label = phrases.base.send

    def action_object_name(self):
        return self.get_object().email

    @property
    def action_back_url(self):
        return self.get_object().team.orga_urls.base

    def post(self, request, *args, **kwargs):
        self.get_object().send()
        messages.success(request, _("The team invitation was sent again."))
        return redirect(self.request.organiser.orga_urls.base)


class TeamResetPassword(PermissionRequired, ActionConfirmMixin, TemplateView):
    model = Team
    permission_required = "orga.change_teams"
    action_confirm_icon = "key"
    action_confirm_label = phrases.base.password_reset_heading
    action_title = phrases.base.password_reset_heading
    action_text = _(
        "Do your really want to reset this user’s password? They won’t be able to log in until they set a new password."
    )

    def action_object_name(self):
        return f"{self.user.get_display_name()} ({self.user.email})"

    @property
    def action_back_url(self):
        return self.team.orga_urls.base

    def get_permission_object(self):
        return self.request.organiser

    @context
    @cached_property
    def team(self):
        return get_object_or_404(
            self.request.organiser.teams.all(), pk=self.kwargs["pk"]
        )

    @context
    @cached_property
    def user(self):
        return get_object_or_404(self.team.members.all(), pk=self.kwargs["user_pk"])

    def post(self, request, *args, **kwargs):
        try:
            self.user.reset_password(event=None, user=self.request.user)
            messages.success(self.request, phrases.orga.password_reset_success)
        except SendMailException:  # pragma: no cover
            messages.error(self.request, phrases.orga.password_reset_fail)
        return redirect(self.request.organiser.orga_urls.base)


class TeamList(PermissionRequired, ListView):
    template_name = "orga/organiser/team_list.html"
    model = Team
    permission_required = "orga.change_teams"
    context_object_name = "teams"

    def get_queryset(self):
        return self.request.organiser.teams.all().order_by("-all_events", "-id")

    def get_permission_object(self):
        return self.request.organiser


class OrganiserDetail(PermissionRequired, CreateOrUpdateView):
    template_name = "orga/organiser/detail.html"
    model = Organiser
    permission_required = "orga.change_organiser_settings"
    form_class = OrganiserForm

    def get_object(self, queryset=None):
        return getattr(self.request, "organiser", None)

    @cached_property
    def object(self):
        return self.get_object()

    def get_success_url(self):
        messages.success(self.request, phrases.base.saved)
        return self.request.path


class OrganiserDelete(PermissionRequired, ActionConfirmMixin, DetailView):
    permission_required = "person.is_administrator"
    model = Organiser
    action_text = (
        _(
            "ALL related data for ALL events, such as proposals, and speaker profiles, and uploads, "
            "will also be deleted and cannot be restored."
        )
        + " "
        + phrases.base.delete_warning
    )

    def get_object(self, queryset=None):
        return getattr(self.request, "organiser", None)

    def action_object_name(self):
        return _("Organiser") + f": {self.get_object().name}"

    @property
    def action_back_url(self):
        return self.get_object().orga_urls.base

    def post(self, *args, **kwargs):
        organiser = self.get_object()
        organiser.shred(person=self.request.user)
        return HttpResponseRedirect(reverse("orga:event.list"))


def get_speaker_access_events_for_user(*, user, organiser):
    events = set()
    for team in user.teams.filter(organiser=organiser):
        if team.can_change_submissions:
            if team.all_events:
                # This user has access to all speakers for all events,
                # so we can cut our logic short here.
                return organiser.events.all()
            else:
                events.update(team.events.values_list("pk", flat=True))
        elif team.is_reviewer:
            # Reviewers *can* have access to speakers, but they do not necessarily
            # do, so we need to check permissions for each event.
            if not team.limit_tracks.exists():
                for event in team.events:
                    if user.has_perm("orga.view_speakers", event):
                        events.add(event.pk)
    return Event.objects.filter(pk__in=events)


@method_decorator(scopes_disabled(), "dispatch")
class OrganiserSpeakerList(
    PermissionRequired, Sortable, Filterable, PaginationMixin, ListView
):
    template_name = "orga/organiser/speaker_list.html"
    permission_required = "orga.view_organiser_speakers"
    context_object_name = "speakers"
    default_filters = ("email__icontains", "name__icontains")
    sortable_fields = ("email", "name", "accepted_submission_count", "submission_count")
    default_sort_field = "name"

    def get_permission_object(self):
        return self.request.organiser

    @context
    @cached_property
    def filter_form(self):
        return UserSpeakerFilterForm(self.request.GET, events=self.events)

    @context
    @cached_property
    def events(self):
        return get_speaker_access_events_for_user(
            user=self.request.user, organiser=self.request.organiser
        )

    def get_queryset(self):
        events = self.events
        if (
            self.filter_form.fields.get("events")
            and self.filter_form.is_valid()
            and self.filter_form.cleaned_data.get("events")
        ):
            events = self.filter_form.cleaned_data["events"]

        qs = (
            User.objects.filter(profiles__event__in=events)
            .prefetch_related("profiles", "profiles__event")
            .annotate(
                submission_count=Count(
                    "submissions",
                    filter=Q(submissions__event__in=events),
                    distinct=True,
                ),
                accepted_submission_count=Count(
                    "submissions",
                    filter=Q(submissions__event__in=events)
                    & Q(submissions__state__in=SubmissionStates.accepted_states),
                    distinct=True,
                ),
            )
        )

        qs = self.filter_queryset(qs)
        role = self.request.GET.get("role") or "speaker"
        if role == "speaker":
            qs = qs.filter(accepted_submission_count__gt=0)
        elif role == "submitter":
            qs = qs.filter(accepted_submission_count=0)

        qs = qs.order_by("id").distinct()
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
            user=request.user, organiser=request.organiser
        )
        users = (
            User.objects.filter(profiles__event__in=events)
            .filter(Q(name__icontains=search) | Q(email__icontains=search))
            .distinct()[:8]
        )
        users = list(users)

    return JsonResponse(
        {
            "count": len(users),
            "results": [{"email": user.email, "name": user.name} for user in users],
        }
    )
