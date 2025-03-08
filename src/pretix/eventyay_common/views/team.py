from urllib.parse import urljoin

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from pretix.base.models import Team
from pretix.control.views.organizer import OrganizerDetailViewMixin

from ...control.forms.organizer_forms import TeamForm
from ...control.permissions import OrganizerPermissionRequiredMixin
from ..tasks import send_team_webhook


class TeamListView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, ListView
):
    model = Team
    template_name = "eventyay_common/organizers/teams/teams.html"
    context_object_name = "teams"
    permission = "can_change_teams"

    def get_queryset(self):
        return self.request.organizer.teams.all().order_by("name")


class TeamCreateView(
    OrganizerDetailViewMixin, CreateView, OrganizerPermissionRequiredMixin
):
    model = Team
    template_name = "eventyay_common/organizers/teams/team_edit.html"
    form_class = TeamForm
    permission = "can_change_teams"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organizer"] = self.request.organizer
        return kwargs

    def get_object(self, queryset=None):
        return get_object_or_404(
            Team, organizer=self.request.organizer, pk=self.kwargs.get("team")
        )

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, gettext_lazy("New team is created."))
        form.instance.organizer = self.request.organizer
        response = super().form_valid(form)
        form.instance.members.add(self.request.user)
        # Trigger talk's webhook to create team in talk component
        team_data = {
            "organiser_slug": self.request.organizer.slug,
            "name": self.object.name,
            "all_events": self.object.all_events,
            "can_create_events": self.object.can_create_events,
            "can_change_teams": self.object.can_change_teams,
            "can_change_organizer_settings": self.object.can_change_organizer_settings,
            "can_change_event_settings": self.object.can_change_event_settings,
            "action": "create",
        }
        send_team_webhook.delay(user_id=self.request.user.id, team=team_data)
        return response

    def form_invalid(self, form):
        messages.error(
            self.request,
            gettext_lazy("Something went wrong, your changes could not be saved."),
        )
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse(
            "eventyay_common:organizer.teams",
            kwargs={"organizer": self.request.organizer.slug},
        )


class TeamUpdateView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, UpdateView
):
    model = Team
    template_name = "eventyay_common/organizers/teams/team_edit.html"
    context_object_name = "team"
    form_class = TeamForm
    permission = "can_change_teams"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organizer"] = self.request.organizer
        return kwargs

    def get_object(self, queryset=None):
        self.object = get_object_or_404(
            Team, organizer=self.request.organizer, pk=self.kwargs.get("team")
        )
        self.old_name = self.object.name
        return self.object

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["talk_edit_url"] = urljoin(
            settings.TALK_HOSTNAME, f"orga/organiser/{self.request.organizer.slug}"
        )
        return ctx

    def get_success_url(self):
        return reverse(
            "eventyay_common:organizer.teams",
            kwargs={"organizer": self.request.organizer.slug},
        )

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, gettext_lazy("Saved."))
        form.instance.organizer = self.request.organizer
        response = super().form_valid(form)
        # Trigger talk's webhook to create team in talk component
        team_data = {
            "organiser_slug": self.request.organizer.slug,
            "name": self.object.name,
            "old_name": self.old_name,
            "all_events": self.object.all_events,
            "can_create_events": self.object.can_create_events,
            "can_change_teams": self.object.can_change_teams,
            "can_change_organizer_settings": self.object.can_change_organizer_settings,
            "can_change_event_settings": self.object.can_change_event_settings,
            "action": "update",
        }
        send_team_webhook.delay(user_id=self.request.user.id, team=team_data)
        return response

    def form_invalid(self, form):
        messages.error(
            self.request,
            gettext_lazy("Something went wrong, your changes could not be saved."),
        )
        return super().form_invalid(form)


class TeamDeleteView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DeleteView
):
    model = Team
    template_name = "eventyay_common/organizers/teams/team_delete.html"
    context_object_name = "team"
    permission = "can_change_teams"

    def get_object(self, queryset=None):
        return get_object_or_404(
            Team, organizer=self.request.organizer, pk=self.kwargs.get("team")
        )

    def get_context_data(self, *args, **kwargs) -> dict:
        context = super().get_context_data(*args, **kwargs)
        context["possible"] = self.can_deleted()
        return context

    def can_deleted(self) -> bool:
        return (
            self.request.organizer.teams.exclude(pk=self.kwargs.get("team"))
            .filter(can_change_teams=True, members__isnull=False)
            .exists()
        )

    @transaction.atomic
    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object = self.get_object()
        if self.can_deleted():
            self.object.delete()
            team_data = {
                "organiser_slug": self.request.organizer.slug,
                "name": self.object.name,
                "action": "delete",
            }
            send_team_webhook.delay(user_id=self.request.user.id, team=team_data)
            messages.success(
                self.request, gettext_lazy("The selected team is deleted.")
            )
            return redirect(success_url)
        else:
            messages.error(
                self.request, gettext_lazy("The selected team cannot be deleted.")
            )
            return redirect(success_url)

    def get_success_url(self):
        return reverse(
            "eventyay_common:organizer.teams",
            kwargs={
                "organizer": self.request.organizer.slug,
            },
        )
