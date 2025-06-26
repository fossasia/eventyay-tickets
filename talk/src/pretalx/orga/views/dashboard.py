from django.db.models import Count, Q
from django.shortcuts import redirect
from django.template.defaultfilters import timeuntil
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy
from django.views.generic import TemplateView
from django_context_decorator import context
from django_scopes import scopes_disabled

from pretalx.common.models.log import ActivityLog
from pretalx.common.text.phrases import phrases
from pretalx.common.views.mixins import EventPermissionRequired, PermissionRequired
from pretalx.event.models import Event, Organiser
from pretalx.event.stages import get_stages
from pretalx.submission.models import Submission, SubmissionStates
from pretalx.submission.rules import get_missing_reviews


def start_redirect_view(request):
    with scopes_disabled():
        orga_events = set(request.user.get_events_with_any_permission())
        speaker_events = set(
            Event.objects.filter(submissions__speakers__in=[request.user])
        )

    # Users with only one event, in only one role, are redirected to that event
    if len(orga_events | speaker_events) == 1 and not (orga_events and speaker_events):
        if orga_events:
            return redirect(orga_events.pop().orga_urls.base)
        return redirect(speaker_events.pop().urls.user_submissions)

    return redirect(reverse("orga:event.list"))


class DashboardEventListView(TemplateView):
    template_name = "orga/event_list.html"

    @property
    def base_queryset(self):
        return self.request.user.get_events_with_any_permission()

    @cached_property
    def queryset(self):
        qs = self.base_queryset.annotate(
            submission_count=Count(
                "submissions",
                filter=Q(
                    submissions__state__in=[
                        state
                        for state in SubmissionStates.display_values.keys()
                        if state
                        not in (SubmissionStates.DELETED, SubmissionStates.DRAFT)
                    ]
                ),
            )
        ).order_by("-date_from")
        if search := self.request.GET.get("q"):
            qs = qs.filter(Q(name__icontains=search) | Q(slug__icontains=search))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_orga_events"] = []
        context["past_orga_events"] = []
        for event in self.queryset:
            if event.date_to >= now().date():
                context["current_orga_events"].insert(0, event)
            else:
                context["past_orga_events"].append(event)
        context["speaker_events"] = (
            Event.objects.filter(submissions__speakers__in=[self.request.user])
            .distinct()
            .order_by("-date_from")
        )
        return context


class DashboardOrganiserEventListView(PermissionRequired, DashboardEventListView):
    permission_required = "event.view_organiser"

    def get_permission_object(self):
        return self.request.organiser

    @property
    def base_queryset(self):
        return self.request.organiser.events.all()

    @context
    def hide_speaker_events(self):
        return True


class DashboardOrganiserListView(PermissionRequired, TemplateView):
    template_name = "orga/organiser/list.html"
    permission_required = "event.list_organiser"

    def filter_organiser(self, organiser, query):
        name = (
            {"en": organiser.name}
            if isinstance(organiser.name, str)
            else organiser.name.data
        )
        name = {"en": name} if isinstance(name, str) else name
        return query in organiser.slug or any(query in value for value in name.values())

    @context
    def organisers(self):
        if self.request.user.is_administrator:
            orgs = Organiser.objects.all()
        else:
            orgs = Organiser.objects.filter(
                pk__in={
                    team.organiser_id
                    for team in self.request.user.teams.filter(
                        can_change_organiser_settings=True
                    )
                }
            )
        orgs = orgs.annotate(
            event_count=Count("events", distinct=True),
            team_count=Count("teams", distinct=True),
        )
        query = self.request.GET.get("q")
        if not query:
            return orgs
        query = query.lower().strip()
        return [org for org in orgs if self.filter_organiser(org, query)]


class EventDashboardView(EventPermissionRequired, TemplateView):
    template_name = "orga/event/dashboard.html"
    permission_required = "event.orga_access_event"

    def get_cfp_tiles(self, _now, can_change_submissions=False):
        result = []
        if self.request.event.cfp.is_open:
            result.append(
                {
                    "url": self.request.event.cfp.urls.public,
                    "large": phrases.cfp.go_to_cfp,
                    "priority": 20,
                }
            )
        max_deadline = self.request.event.cfp.max_deadline
        if max_deadline and _now < max_deadline:
            result.append(
                {
                    "large": timeuntil(max_deadline),
                    "small": _("until the CfP ends"),
                    "priority": 40,
                }
            )
            draft_proposals = Submission.all_objects.filter(
                state=SubmissionStates.DRAFT, event=self.request.event
            ).count()
            if draft_proposals and can_change_submissions:
                result.append(
                    {
                        "large": draft_proposals,
                        "small": ngettext_lazy(
                            "unsubmitted proposal draft",
                            "unsubmitted proposal drafts",
                            draft_proposals,
                        ),
                        "priority": 50,
                        "url": self.request.event.orga_urls.send_drafts_reminder,
                        "left": {
                            "text": _("Send reminder"),
                            "url": self.request.event.orga_urls.send_drafts_reminder,
                            "color": "info",
                        },
                    }
                )
        return result

    def get_review_tiles(self, can_change_settings):
        result = []
        review_count = self.request.event.reviews.count()
        if review_count:
            active_reviewers = (
                self.request.event.reviewers.filter(reviews__isnull=False)
                .order_by("id")
                .distinct()
                .count()
            )
            result.append(
                {"large": review_count, "small": _("Reviews"), "priority": 60}
            )
            result.append(
                {
                    "large": active_reviewers,
                    "small": _("Active reviewers"),
                    "url": (
                        self.request.event.organiser.orga_urls.teams
                        if can_change_settings
                        else None
                    ),
                    "priority": 60,
                }
            )
        is_reviewer = self.request.event.teams.filter(
            members__in=[self.request.user], is_reviewer=True
        ).exists()
        if is_reviewer:
            reviews_missing = get_missing_reviews(
                self.request.event, self.request.user
            ).count()
            if reviews_missing:
                result.append(
                    {
                        "large": reviews_missing,
                        "small": ngettext_lazy(
                            "proposal is waiting for your review.",
                            "proposals are waiting for your review.",
                            reviews_missing,
                        ),
                        "url": self.request.event.orga_urls.reviews,
                        "priority": 21,
                    }
                )
        return result

    @context
    def history(self):
        return ActivityLog.objects.filter(event=self.request.event).select_related(
            "person", "event"
        )[:20]

    def get_context_data(self, **kwargs):
        # Tiles can have priorities
        # Priorities are meant to be between 0 and 100
        # 0 is the first tile, the go-live tile
        # 100+ is whatever can go to the very end
        # actions should be between 10 and 30, with 20 being the "go to cfp" action
        # general stats start at 50
        result = super().get_context_data(**kwargs)
        event = self.request.event
        stages = get_stages(event)
        result["timeline"] = stages.values()
        result["go_to_target"] = (
            "schedule" if stages["REVIEW"]["phase"] == "done" else "cfp"
        )
        _now = now()
        today = _now.date()
        can_change_settings = self.request.user.has_perm(
            "event.change_settings.event", event
        )
        can_change_submissions = self.request.user.has_perm(
            "submission.orga_update_submission", event
        )
        result["tiles"] = self.get_cfp_tiles(
            _now, can_change_submissions=can_change_submissions
        )
        if today < event.date_from:
            days = (event.date_from - today).days
            result["tiles"].append(
                {
                    "large": days,
                    "small": ngettext_lazy(
                        "day until event start", "days until event start", days
                    ),
                    "priority": 10,
                }
            )
        elif today > event.date_to:
            days = (today - event.date_from).days
            result["tiles"].append(
                {
                    "large": days,
                    "small": ngettext_lazy(
                        "day since event end", "days since event end", days
                    ),
                    "priority": 80,
                }
            )
        elif event.date_to != event.date_from:
            day = (today - event.date_from).days + 1
            result["tiles"].append(
                {
                    "large": _("Day {number}").format(number=day),
                    "small": _("of {total_days} days").format(
                        total_days=(event.date_to - event.date_from).days + 1
                    ),
                    "url": event.urls.schedule + f"#{today.isoformat()}",
                    "priority": 10,
                }
            )
        if event.current_schedule:
            result["tiles"].append(
                {
                    "large": event.current_schedule.version,
                    "small": _("current schedule"),
                    "url": event.urls.schedule,
                    "priority": 25,
                }
            )

        talk_count = event.talks.count()
        accepted_count = event.submissions.filter(
            state=SubmissionStates.ACCEPTED
        ).count()
        submission_count = event.submissions.count()
        pending_state_submissions = event.submissions.filter(
            pending_state__isnull=False
        ).count()
        if talk_count or accepted_count:
            confirmed_count = event.submissions.filter(
                state=SubmissionStates.CONFIRMED
            ).count()
            result["tiles"].append(
                {
                    # Don’t show 0 here for events that do not use the scheduling
                    # component, instead show accepted + confirmed
                    "large": talk_count or (accepted_count + confirmed_count),
                    "small": ngettext_lazy("session", "sessions", talk_count),
                    "url": event.orga_urls.submissions
                    + f"?state={SubmissionStates.ACCEPTED}&state={SubmissionStates.CONFIRMED}",
                    "priority": 55,
                    "right": {
                        "text": str(_("unconfirmed")) + f": {accepted_count}",
                        "url": event.orga_urls.submissions
                        + f"?state={SubmissionStates.ACCEPTED}",
                        "color": "error" if accepted_count else "info",
                    },
                    "left": {
                        "text": str(_("confirmed")) + f": {confirmed_count}",
                        "url": event.orga_urls.submissions,
                        "color": "success",
                    },
                }
            )
        elif submission_count:
            count = event.submissions.count()
            result["tiles"].append(
                {
                    "large": count,
                    "small": ngettext_lazy("proposal", "proposals", count),
                    "url": event.orga_urls.submissions,
                    "priority": 60,
                }
            )
        if pending_state_submissions and pending_state_submissions > 0:
            states = "&".join(
                [
                    f"state=pending_state__{state}"
                    for state, __ in SubmissionStates.get_choices()
                    if state not in (SubmissionStates.DRAFT, SubmissionStates.DELETED)
                ]
            )
            result["tiles"].append(
                {
                    "large": pending_state_submissions,
                    "small": ngettext_lazy(
                        "submission with pending changes",
                        "submissions with pending changes",
                        pending_state_submissions,
                    ),
                    "url": event.orga_urls.submissions + f"?{states}",
                    "priority": 56,
                }
            )
        submitter_count = event.submitters.count()
        speaker_count = event.speakers.count()
        rejected_count = (
            event.submitters.filter(submissions__state=SubmissionStates.REJECTED)
            .distinct()
            .count()
        )
        if speaker_count:
            result["tiles"].append(
                {
                    "large": speaker_count,
                    "small": ngettext_lazy("speaker", "speakers", speaker_count),
                    "url": event.orga_urls.speakers + "?role=true",
                    "priority": 56,
                    "right": {
                        "text": _("rejected") + f": {rejected_count}",
                        "url": event.orga_urls.speakers + "?role=false",
                        "color": "error",
                    },
                    "left": {
                        "text": phrases.submission.submitted + f": {submitter_count}",
                        "url": event.orga_urls.speakers,
                        "color": "success",
                    },
                }
            )
        else:
            result["tiles"].append(
                {
                    "large": submitter_count,
                    "small": ngettext_lazy("submitter", "submitters", submitter_count),
                    "url": event.orga_urls.speakers,
                    "priority": 60,
                }
            )
        count = event.queued_mails.filter(sent__isnull=False).count()
        result["tiles"].append(
            {
                "large": count,
                "small": ngettext_lazy("sent email", "sent emails", count),
                "url": event.orga_urls.sent_mails,
                "priority": 80,
            }
        )
        result["tiles"] += self.get_review_tiles(
            can_change_settings=can_change_settings
        )
        result["tiles"].sort(key=lambda tile: tile.get("priority") or 100)
        return result
