import json
from collections import Counter
from operator import itemgetter

from dateutil import rrule
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.contrib.syndication.views import Feed
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Subquery
from django.forms.models import BaseModelFormSet, inlineformset_factory
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import feedgenerator
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, ListView, TemplateView, UpdateView, View
from django_context_decorator import context

from pretalx.agenda.permissions import is_submission_visible
from pretalx.common.exceptions import SubmissionError
from pretalx.common.forms.fields import SizeFileInput
from pretalx.common.models import ActivityLog
from pretalx.common.text.phrases import phrases
from pretalx.common.views import CreateOrUpdateView
from pretalx.common.views.mixins import (
    ActionConfirmMixin,
    ActionFromUrl,
    EventPermissionRequired,
    PaginationMixin,
    PermissionRequired,
    Sortable,
)
from pretalx.mail.models import MailTemplateRoles
from pretalx.orga.forms.submission import (
    AddSpeakerForm,
    AddSpeakerInlineForm,
    AnonymiseForm,
    SubmissionForm,
    SubmissionStateChangeForm,
)
from pretalx.person.models import User
from pretalx.submission.forms import (
    QuestionsForm,
    ResourceForm,
    SubmissionFilterForm,
    TagForm,
)
from pretalx.submission.models import (
    Feedback,
    Resource,
    Submission,
    SubmissionStates,
    Tag,
)


class SubmissionViewMixin(PermissionRequired):
    def get_queryset(self):
        return Submission.objects.filter(event=self.request.event)

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(),
            code__iexact=self.kwargs.get("code"),
        )

    def get_permission_object(self):
        return self.object

    @cached_property
    def object(self):
        return self.get_object()

    @context
    def submission(self):
        return self.object

    @context
    @cached_property
    def has_anonymised_review(self):
        return self.request.event.review_phases.filter(
            can_see_speaker_names=False
        ).exists()

    @context
    @cached_property
    def is_publicly_visible(self):
        # check if the anonymous user could see this submission's page
        return is_submission_visible(None, self.object)


class ReviewerSubmissionFilter:
    @cached_property
    def limit_tracks(self):
        if self.user_permissions == {"is_reviewer"}:
            teams = self.request.user.teams.filter(
                Q(all_events=True)
                | Q(Q(all_events=False) & Q(limit_events__in=[self.request.event])),
                limit_tracks__isnull=False,
                organiser=self.request.event.organiser,
            ).prefetch_related("limit_tracks", "limit_tracks__event")
            tracks = set()
            for team in teams:
                tracks.update(team.limit_tracks.filter(event=self.request.event))
            return tracks

    def limit_for_reviewers(self, queryset):
        phase = self.request.event.active_review_phase
        if not phase:
            return queryset

        if phase.proposal_visibility == "assigned":
            return queryset.filter(is_assigned__gte=1)

        if self.limit_tracks:
            return queryset.filter(track__in=self.limit_tracks)
        return queryset

    @cached_property
    def user_permissions(self):
        return self.request.user.get_permissions_for_event(self.request.event)

    def get_queryset(self, for_review=False):
        queryset = (
            self.request.event.submissions.all()
            .select_related("submission_type", "event", "track")
            .prefetch_related("speakers")
        )
        if "is_reviewer" in self.user_permissions or for_review:
            assigned = self.request.user.assigned_reviews.filter(
                event=self.request.event, pk=OuterRef("pk")
            )
            queryset = queryset.annotate(is_assigned=Exists(Subquery(assigned)))
        if self.user_permissions == {"is_reviewer"}:
            queryset = self.limit_for_reviewers(queryset)
        return queryset


class SubmissionStateChange(SubmissionViewMixin, FormView):
    form_class = SubmissionStateChangeForm
    permission_required = "orga.change_submission_state"
    template_name = "orga/submission/state_change.html"
    TARGETS = {
        "submit": SubmissionStates.SUBMITTED,
        "accept": SubmissionStates.ACCEPTED,
        "reject": SubmissionStates.REJECTED,
        "confirm": SubmissionStates.CONFIRMED,
        "delete": SubmissionStates.DELETED,
        "withdraw": SubmissionStates.WITHDRAWN,
        "cancel": SubmissionStates.CANCELED,
    }

    @cached_property
    def _target(self) -> str:
        """Returns one of
        submit|accept|reject|confirm|delete|withdraw|cancel."""
        return self.TARGETS[self.request.resolver_match.url_name.split(".")[-1]]

    @context
    def target(self):
        return self._target

    def do(self, force=False, pending=False):
        if pending:
            self.object.pending_state = self._target
            self.object.save()
            if self.object.pending_state in SubmissionStates.accepted_states:
                # allow configureability of pending accepted/confirmed talks
                self.object.update_talk_slots()
        else:
            method = getattr(self.object, SubmissionStates.method_names[self._target])
            method(person=self.request.user, force=force, orga=True)

    @transaction.atomic
    def form_valid(self, form):
        if self._target == self.object.state and not self.object.pending_state:
            messages.info(
                self.request,
                _(
                    "Somebody else was faster than you: this proposal was already in the state you wanted to change it to."
                ),
            )
            return redirect(self.get_success_url())

        current = self.object.state
        pending = form.cleaned_data.get("pending")
        try:
            self.do(pending=pending)
        except SubmissionError:
            self.do(force=True, pending=pending)

        if pending:
            return redirect(self.get_success_url())

        check_mail_template = {
            (
                SubmissionStates.ACCEPTED,
                SubmissionStates.REJECTED,
            ): self.request.event.get_mail_template(
                MailTemplateRoles.SUBMISSION_ACCEPT
            ),
            (
                SubmissionStates.REJECTED,
                SubmissionStates.ACCEPTED,
            ): self.request.event.get_mail_template(
                MailTemplateRoles.SUBMISSION_REJECT
            ),
        }
        if template := check_mail_template.get((current, self.object.state)):
            pending_emails = self.request.event.queued_mails.filter(
                template=template,
                sent__isnull=True,
                to_users__in=self.object.speakers.all(),
            )
            if pending_emails.exists():
                messages.warning(
                    self.request,
                    _(
                        "There may be pending emails for this proposal that are now incorrect or outdated."
                    ),
                )
        return redirect(self.get_success_url())

    def get_success_url(self):
        url = self.request.GET.get("next")
        if self.object.state == SubmissionStates.DELETED and (
            not url or self.object.code in url
        ):
            return self.request.event.orga_urls.submissions
        elif url and url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            return url
        return self.request.event.orga_urls.submissions

    @context
    def next(self):
        return self.request.GET.get("next")


class SubmissionSpeakersDelete(SubmissionViewMixin, View):
    permission_required = "submission.edit_speaker_list"

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.object
        speaker = get_object_or_404(User, pk=request.GET.get("id"))

        if submission in speaker.submissions.all():
            speaker.submissions.remove(submission)
            submission.log_action(
                "pretalx.submission.speakers.remove", person=request.user, orga=True
            )
            messages.success(
                request, _("The speaker has been removed from the proposal.")
            )
        else:
            messages.warning(request, _("The speaker was not part of this proposal."))
        return redirect(submission.orga_urls.speakers)


class SubmissionSpeakers(ReviewerSubmissionFilter, SubmissionViewMixin, FormView):
    template_name = "orga/submission/speakers.html"
    permission_required = "orga.view_speakers"
    form_class = AddSpeakerInlineForm

    @context
    @cached_property
    def speakers(self):
        submission = self.object
        return [
            {
                "user": speaker,
                "profile": speaker.event_profile(submission.event),
                "other_submissions": speaker.submissions.filter(
                    event=submission.event
                ).exclude(code=submission.code),
            }
            for speaker in submission.speakers.all()
        ]

    def form_valid(self, form):
        if email := form.cleaned_data.get("email"):
            speaker = self.object.add_speaker(
                email=email,
                name=form.cleaned_data.get("name"),
                locale=form.cleaned_data.get("locale"),
                user=self.request.user,
            )
            messages.success(
                self.request, _("The speaker has been added to the proposal.")
            )
            return redirect(speaker.event_profile(self.request.event).orga_urls.base)
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        return kwargs

    def get_success_url(self):
        return self.object.orga_urls.speakers


class SubmissionContent(
    ActionFromUrl, ReviewerSubmissionFilter, SubmissionViewMixin, CreateOrUpdateView
):
    model = Submission
    form_class = SubmissionForm
    template_name = "orga/submission/content.html"
    permission_required = "orga.view_submissions"

    def get_object(self):
        try:
            return super().get_object()
        except Http404 as not_found:
            if self.request.path.rstrip("/").endswith("/new"):
                return None
            return not_found

    @cached_property
    def write_permission_required(self):
        if self.kwargs.get("code"):
            return "submission.edit_submission"
        return "orga.create_submission"

    @context
    def size_warning(self):
        return SizeFileInput.get_size_warning()

    @cached_property
    def _formset(self):
        formset_class = inlineformset_factory(
            Submission,
            Resource,
            form=ResourceForm,
            formset=BaseModelFormSet,
            can_delete=True,
            extra=0,
        )
        submission = self.get_object()
        return formset_class(
            self.request.POST if self.request.method == "POST" else None,
            files=self.request.FILES if self.request.method == "POST" else None,
            queryset=(
                submission.resources.all() if submission else Resource.objects.none()
            ),
            prefix="resource",
        )

    @context
    def formset(self):
        return self._formset

    @context
    @cached_property
    def new_speaker_form(self):
        if not self.get_object():
            return AddSpeakerForm(
                data=self.request.POST if self.request.method == "POST" else None,
                event=self.request.event,
                prefix="speaker",
            )

    @cached_property
    def _questions_form(self):
        submission = self.get_object()
        form_kwargs = self.get_form_kwargs()
        return QuestionsForm(
            self.request.POST if self.request.method == "POST" else None,
            files=self.request.FILES if self.request.method == "POST" else None,
            target="submission",
            submission=submission,
            event=self.request.event,
            for_reviewers=(
                not self.request.user.has_perm(
                    "orga.change_submissions", self.request.event
                )
                and self.request.user.has_perm(
                    "orga.view_review_dashboard", self.request.event
                )
            ),
            readonly=form_kwargs["read_only"],
        )

    @context
    def questions_form(self):
        return self._questions_form

    def save_formset(self, obj):
        if not self._formset.is_valid():
            return False

        for form in self._formset.initial_forms:
            if form in self._formset.deleted_forms:
                if not form.instance.pk:
                    continue
                obj.log_action(
                    "pretalx.submission.resource.delete",
                    person=self.request.user,
                    data={"id": form.instance.pk},
                )
                form.instance.delete()
                form.instance.pk = None
            elif form.has_changed():
                form.instance.submission = obj
                form.save()
                change_data = {
                    key: form.cleaned_data.get(key) for key in form.changed_data
                }
                change_data["id"] = form.instance.pk
                obj.log_action(
                    "pretalx.submission.resource.update", person=self.request.user
                )

        extra_forms = [
            form
            for form in self._formset.extra_forms
            if form.has_changed
            and not self._formset._should_delete_form(form)
            and form.is_valid()
        ]
        for form in extra_forms:
            form.instance.submission = obj
            form.save()
            obj.log_action(
                "pretalx.submission.resource.create",
                person=self.request.user,
                orga=True,
                data={"id": form.instance.pk},
            )

        return True

    def get_permission_required(self):
        if "code" in self.kwargs:
            return ["orga.view_submissions"]
        return ["orga.create_submission"]

    @property
    def permission_object(self):
        return self.object or self.request.event

    def get_permission_object(self):
        return self.permission_object

    def get_success_url(self) -> str:
        return self.object.orga_urls.base

    @transaction.atomic()
    def form_valid(self, form):
        created = not self.object
        self.object = form.instance
        self._questions_form.submission = self.object
        if not self._questions_form.is_valid():
            return self.get(self.request, *self.args, **self.kwargs)
        form.instance.event = self.request.event
        form.save()
        self._questions_form.save()

        if created:
            if not self.new_speaker_form.is_valid():
                if self.new_speaker_form.errors:
                    messages.error(self.request, self.new_speaker_form.errors[0])
                return self.form_invalid(form)
            elif email := self.new_speaker_form.cleaned_data["email"]:
                form.instance.add_speaker(
                    email=email,
                    name=self.new_speaker_form.cleaned_data["name"],
                    locale=self.new_speaker_form.cleaned_data.get("locale"),
                    user=self.request.user,
                )
        else:
            formset_result = self.save_formset(form.instance)
            if not formset_result:
                return self.get(self.request, *self.args, **self.kwargs)
            messages.success(self.request, _("The proposal has been updated!"))
        if form.has_changed():
            action = "pretalx.submission." + ("create" if created else "update")
            form.instance.log_action(action, person=self.request.user, orga=True)
            self.request.event.cache.set("rebuild_schedule_export", True, None)
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        instance = kwargs.get("instance")
        kwargs["anonymise"] = getattr(
            instance, "pk", None
        ) and not self.request.user.has_perm("orga.view_speakers", instance)
        kwargs["read_only"] = kwargs["read_only"] or kwargs["anonymise"]
        return kwargs

    @context
    @cached_property
    def can_edit(self):
        return self.object and self.request.user.has_perm(
            "orga.change_submissions", self.request.event
        )


class BaseSubmissionList(Sortable, ReviewerSubmissionFilter, PaginationMixin, ListView):
    model = Submission
    context_object_name = "submissions"
    filter_fields = ()
    sortable_fields = (
        "code",
        "title",
        "state",
        "is_featured",
        "submission_type__name",
        "track__name",
    )
    usable_states = None

    def get_filter_form(self):
        return SubmissionFilterForm(
            data=self.request.GET,
            event=self.request.event,
            usable_states=self.usable_states,
            limit_tracks=self.limit_tracks,
            search_fields=self.get_default_filters(),
        )

    @context
    @cached_property
    def filter_form(self):
        return self.get_filter_form()

    def get_default_filters(self, *args, **kwargs):
        default_filters = {"code__icontains", "title__icontains"}
        if self.request.user.has_perm("orga.view_speakers", self.request.event):
            default_filters.add("speakers__name__icontains")
        return default_filters

    def _get_base_queryset(self, for_review=False):
        # If somebody has *only* reviewer permissions for this event, they can only
        # see the proposals they can review.
        qs = super().get_queryset(for_review=for_review).order_by("-id")
        if not self.filter_form.is_valid():
            return qs
        return self.filter_form.filter_queryset(qs)

    def get_queryset(self):
        return self.sort_queryset(self._get_base_queryset()).distinct()


class SubmissionList(EventPermissionRequired, BaseSubmissionList):
    template_name = "orga/submission/list.html"
    permission_required = "orga.view_submissions"
    paginate_by = 25
    default_sort_field = "state"
    secondary_sort = {"state": ("pending_state",)}

    @context
    def show_submission_types(self):
        return self.request.event.submission_types.all().count() > 1

    @context
    @cached_property
    def pending_changes(self):
        return self.request.event.submissions.filter(
            pending_state__isnull=False
        ).count()

    @context
    def show_tracks(self):
        if self.request.event.get_feature_flag("use_tracks"):
            if self.limit_tracks:
                return len(self.limit_tracks) > 1
            return self.request.event.tracks.all().count() > 1


class FeedbackList(SubmissionViewMixin, PaginationMixin, ListView):
    template_name = "orga/submission/feedback_list.html"
    context_object_name = "feedback"
    paginate_by = 25
    permission_required = "submission.view_feedback"

    def get_queryset(self):
        return self.submission.feedback.all().order_by("pk")

    def get_object(self):
        return get_object_or_404(
            Submission.objects.filter(event=self.request.event),
            code__iexact=self.kwargs.get("code"),
        )

    @cached_property
    def submission(self):
        return self.get_object()

    def get_permission_object(self):
        return self.submission


class ToggleFeatured(SubmissionViewMixin, View):
    permission_required = "orga.change_submissions"

    def get_permission_object(self):
        return self.object or self.request.event

    def post(self, *args, **kwargs):
        self.object.is_featured = not self.object.is_featured
        self.object.save(update_fields=["is_featured"])
        return HttpResponse()


class Anonymise(SubmissionViewMixin, UpdateView):
    permission_required = "orga.change_submissions"
    template_name = "orga/submission/anonymise.html"
    form_class = AnonymiseForm

    def get_permission_object(self):
        return self.object or self.request.event

    @context
    @cached_property
    def next_unanonymised(self):
        return self.request.event.submissions.filter(
            Q(anonymised_data="{}") | Q(anonymised_data__isnull=True)
        ).first()

    def form_valid(self, form):
        if self.object.is_anonymised:
            message = _("The anonymisation has been updated.")
        else:
            message = _("This proposal is now marked as anonymised.")
        form.save()
        messages.success(self.request, message)
        if self.request.POST.get("action", "save") == "next" and self.next_unanonymised:
            return redirect(self.next_unanonymised.orga_urls.anonymise)
        return redirect(self.object.orga_urls.anonymise)


class SubmissionFeed(PermissionRequired, Feed):
    permission_required = "orga.view_submission"
    feed_type = feedgenerator.Atom1Feed

    def get_object(self, request, *args, **kwargs):
        return request.event

    def title(self, obj):
        return _("{name} proposal feed").format(name=obj.name)

    def link(self, obj):
        return obj.orga_urls.submissions.full()

    def feed_url(self, obj):
        return obj.orga_urls.submission_feed.full()

    def feed_guid(self, obj):
        return obj.orga_urls.submission_feed.full()

    def description(self, obj):
        return _("Updates to the {name} schedule.").format(name=obj.name)

    def items(self, obj):
        return obj.submissions.order_by("-pk")

    def item_title(self, item):
        return _("New {event} proposal: {title}").format(
            event=item.event.name, title=item.title
        )

    def item_link(self, item):
        return item.orga_urls.base.full()

    def item_pubdate(self, item):
        return item.created


class SubmissionStats(PermissionRequired, TemplateView):
    template_name = "orga/submission/stats.html"
    permission_required = "orga.view_submissions"

    def get_permission_object(self):
        return self.request.event

    @context
    def show_submission_types(self):
        return self.request.event.submission_types.all().count() > 1

    @context
    def id_mapping(self):
        data = {
            "type": {
                str(submission_type): submission_type.id
                for submission_type in self.request.event.submission_types.all()
            },
            "state": {
                str(value): key
                for key, value in SubmissionStates.display_values.items()
            },
        }
        if self.show_tracks:
            data["track"] = {
                str(track): track.id for track in self.request.event.tracks.all()
            }
        return json.dumps(data)

    @context
    @cached_property
    def show_tracks(self):
        return (
            self.request.event.get_feature_flag("use_tracks")
            and self.request.event.tracks.all().count() > 1
        )

    @context
    def timeline_annotations(self):
        deadlines = [
            (
                submission_type.deadline.astimezone(self.request.event.tz).strftime(
                    "%Y-%m-%d"
                ),
                str(_("Deadline")) + f" ({submission_type.name})",
            )
            for submission_type in self.request.event.submission_types.filter(
                deadline__isnull=False
            )
        ]
        if self.request.event.cfp.deadline:
            deadlines.append(
                (
                    self.request.event.cfp.deadline.astimezone(
                        self.request.event.tz
                    ).strftime("%Y-%m-%d"),
                    str(_("Deadline")),
                )
            )
        return json.dumps({"deadlines": deadlines})

    @cached_property
    def raw_submission_timeline_data(self):
        talk_ids = self.request.event.submissions.exclude(
            state=SubmissionStates.DELETED
        ).values_list("id", flat=True)
        data = Counter(
            log.timestamp.astimezone(self.request.event.tz).date()
            for log in ActivityLog.objects.filter(
                event=self.request.event,
                action_type="pretalx.submission.create",
                content_type=ContentType.objects.get_for_model(Submission),
                object_id__in=talk_ids,
            )
        )
        dates = data.keys()
        if len(dates) > 1:
            date_range = rrule.rrule(
                rrule.DAILY,
                count=(max(dates) - min(dates)).days + 1,
                dtstart=min(dates),
            )
            return sorted(
                (
                    {"x": date.date().isoformat(), "y": data.get(date.date(), 0)}
                    for date in date_range
                ),
                key=lambda x: x["x"],
            )

    @context
    def submission_timeline_data(self):
        if self.raw_submission_timeline_data:
            return json.dumps(self.raw_submission_timeline_data)
        return ""

    @context
    def total_submission_timeline_data(self):
        if self.raw_submission_timeline_data:
            result = [{"x": 0, "y": 0}]
            for point in self.raw_submission_timeline_data:
                result.append({"x": point["x"], "y": result[-1]["y"] + point["y"]})
            return json.dumps(result[1:])
        return ""

    @context
    @cached_property
    def submission_state_data(self):
        counter = Counter(
            submission.get_state_display()
            for submission in Submission.all_objects.exclude(
                state=SubmissionStates.DRAFT
            ).filter(event=self.request.event)
        )
        return json.dumps(
            sorted(
                [{"label": label, "value": value} for label, value in counter.items()],
                key=itemgetter("label"),
            )
        )

    @context
    def submission_type_data(self):
        counter = Counter(
            str(submission.submission_type)
            for submission in Submission.objects.filter(
                event=self.request.event
            ).select_related("submission_type")
        )
        return json.dumps(
            sorted(
                [{"label": label, "value": value} for label, value in counter.items()],
                key=itemgetter("label"),
            )
        )

    @context
    def submission_track_data(self):
        if self.request.event.get_feature_flag("use_tracks"):
            counter = Counter(
                str(submission.track)
                for submission in Submission.objects.filter(
                    event=self.request.event
                ).select_related("track")
            )
            return json.dumps(
                sorted(
                    [
                        {"label": label, "value": value}
                        for label, value in counter.items()
                    ],
                    key=itemgetter("label"),
                )
            )
        return ""

    @context
    def talk_timeline_data(self):
        talk_ids = self.request.event.submissions.filter(
            state__in=SubmissionStates.accepted_states
        ).values_list("id", flat=True)
        data = Counter(
            log.timestamp.astimezone(self.request.event.tz).date().isoformat()
            for log in ActivityLog.objects.filter(
                event=self.request.event,
                action_type="pretalx.submission.create",
                content_type=ContentType.objects.get_for_model(Submission),
                object_id__in=talk_ids,
            )
        )
        if len(data.keys()) > 1:
            return json.dumps(
                [
                    {"x": point["x"], "y": data.get(point["x"][:10], 0)}
                    for point in self.raw_submission_timeline_data
                ]
            )
        return ""

    @context
    def talk_state_data(self):
        counter = Counter(
            submission.get_state_display()
            for submission in self.request.event.submissions.filter(
                state__in=SubmissionStates.accepted_states
            )
        )
        return json.dumps(
            sorted(
                [{"label": label, "value": value} for label, value in counter.items()],
                key=itemgetter("label"),
            )
        )

    @context
    def talk_type_data(self):
        counter = Counter(
            str(submission.submission_type)
            for submission in self.request.event.submissions.filter(
                state__in=SubmissionStates.accepted_states
            ).select_related("submission_type")
        )
        return json.dumps(
            sorted(
                [{"label": label, "value": value} for label, value in counter.items()],
                key=itemgetter("label"),
            )
        )

    @context
    def talk_track_data(self):
        if self.request.event.get_feature_flag("use_tracks"):
            counter = Counter(
                str(submission.track)
                for submission in self.request.event.submissions.filter(
                    state__in=SubmissionStates.accepted_states
                ).select_related("track")
            )
            return json.dumps(
                sorted(
                    [
                        {"label": label, "value": value}
                        for label, value in counter.items()
                    ],
                    key=itemgetter("label"),
                )
            )
        return ""


class AllFeedbacksList(EventPermissionRequired, PaginationMixin, ListView):
    model = Feedback
    context_object_name = "feedback"
    template_name = "orga/submission/feedbacks_list.html"

    permission_required = "orga.view_submissions"
    paginate_by = 25

    def get_queryset(self):
        return (
            Feedback.objects.order_by("-pk")
            .select_related("talk")
            .filter(talk__event=self.request.event)
        )


class TagList(EventPermissionRequired, PaginationMixin, ListView):
    template_name = "orga/submission/tag_list.html"
    context_object_name = "tags"
    permission_required = "orga.view_submissions"

    def get_queryset(self):
        return self.request.event.tags.all().order_by("tag")


class TagDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = Tag
    form_class = TagForm
    template_name = "orga/submission/tag_form.html"
    permission_required = "orga.view_submissions"
    write_permission_required = "orga.edit_tags"
    create_permission_required = "orga.add_tags"

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.tags

    def get_object(self):
        return self.request.event.tags.filter(pk=self.kwargs.get("pk")).first()

    def get_permission_object(self):
        return self.get_object() or self.request.event

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["event"] = self.request.event
        return result

    def form_valid(self, form):
        form.instance.event = self.request.event
        result = super().form_valid(form)
        messages.success(self.request, phrases.base.saved)
        if form.has_changed():
            action = "pretalx.tag." + ("update" if self.object else "create")
            form.instance.log_action(action, person=self.request.user, orga=True)
        return result


class TagDelete(PermissionRequired, ActionConfirmMixin, TemplateView):
    permission_required = "orga.remove_tags"

    def get_object(self):
        return get_object_or_404(self.request.event.tags, pk=self.kwargs.get("pk"))

    def action_object_name(self):
        return _("Tag") + f": {self.get_object().tag}"

    def action_back_url(self):
        return self.request.event.orga_urls.tags

    def post(self, request, *args, **kwargs):
        tag = self.get_object()

        tag.delete()
        request.event.log_action(
            "pretalx.tag.delete", person=self.request.user, orga=True
        )
        messages.success(request, _("The tag has been deleted."))
        return redirect(self.request.event.orga_urls.tags)


class ApplyPending(EventPermissionRequired, TemplateView):
    permission_required = "orga.change_submissions"
    template_name = "orga/submission/apply_pending.html"

    @cached_property
    def submissions(self):
        return self.request.event.submissions.filter(pending_state__isnull=False)

    @context
    @cached_property
    def submission_count(self):
        return len(self.submissions)

    def post(self, request, *args, **kwargs):
        for submission in self.submissions:
            try:
                submission.apply_pending_state(person=self.request.user)
            except Exception:
                submission.apply_pending_state(person=self.request.user, force=True)
        messages.success(
            self.request,
            str(_("Changed {count} proposal states.")).format(
                count=self.submission_count
            ),
        )
        url = self.request.GET.get("next")
        if url and url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            return redirect(url)
        return redirect(self.request.event.orga_urls.submissions)

    @context
    def next(self):
        return self.request.GET.get("next")
