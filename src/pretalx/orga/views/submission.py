import datetime as dt
import json
from collections import Counter
from contextlib import suppress
from operator import itemgetter

from dateutil import rrule
from django.contrib import messages
from django.contrib.syndication.views import Feed
from django.db import transaction
from django.forms.models import BaseModelFormSet, inlineformset_factory
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import feedgenerator
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now
from django.utils.translation import gettext as _
from django.utils.translation import override
from django.views.generic import ListView, TemplateView, View

from pretalx.common.mixins.views import (
    ActionFromUrl,
    EventPermissionRequired,
    Filterable,
    PermissionRequired,
    Sortable,
)
from pretalx.common.models import ActivityLog
from pretalx.common.urls import build_absolute_uri
from pretalx.common.views import CreateOrUpdateView, context
from pretalx.mail.models import QueuedMail
from pretalx.orga.forms import SubmissionForm
from pretalx.person.forms import OrgaSpeakerForm
from pretalx.person.models import SpeakerProfile, User
from pretalx.submission.forms import QuestionsForm, ResourceForm, SubmissionFilterForm
from pretalx.submission.models import (
    Feedback,
    Resource,
    Submission,
    SubmissionError,
    SubmissionStates,
)


def create_user_as_orga(email, submission=None, name=None):
    form = OrgaSpeakerForm({"name": name, "email": email})
    form.is_valid()

    user = User.objects.create_user(
        password=get_random_string(32),
        email=form.cleaned_data["email"].lower().strip(),
        name=form.cleaned_data["name"].strip(),
        pw_reset_token=get_random_string(32),
        pw_reset_time=now() + dt.timedelta(days=7),
    )
    SpeakerProfile.objects.get_or_create(user=user, event=submission.event)
    with override(submission.content_locale):
        invitation_link = build_absolute_uri(
            "cfp:event.recover",
            kwargs={"event": submission.event.slug, "token": user.pw_reset_token},
        )
        invitation_text = _(
            """Hi!

You have been set as the speaker of a submission to the Call for Participation
of {event}, titled “{title}”. An account has been created for you – please follow
this link to set your account password.

{invitation_link}

Afterwards, you can edit your user profile and see the state of your submission.

The {event} orga crew"""
        ).format(
            event=submission.event.name,
            title=submission.title,
            invitation_link=invitation_link,
        )
        mail = QueuedMail.objects.create(
            event=submission.event,
            reply_to=submission.event.email,
            subject=str(
                _("You have been added to a submission for {event}").format(
                    event=submission.event.name
                )
            ),
            text=invitation_text,
        )
        mail.to_users.add(user)
    return user


class SubmissionViewMixin(PermissionRequired):
    def get_object(self):
        return get_object_or_404(
            Submission.all_objects.filter(event=self.request.event),
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


class SubmissionStateChange(SubmissionViewMixin, TemplateView):
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

    @cached_property
    def is_allowed(self):
        return self._target in SubmissionStates.valid_next_states[self.object.state]

    def do(self, force=False):
        method = getattr(self.object, SubmissionStates.method_names[self._target])
        try:
            method(person=self.request.user, force=force, orga=True)
        except SubmissionError as e:
            messages.error(self.request, e.message)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        if self._target == self.object.state:
            messages.info(
                request,
                _(
                    "Somebody else was faster than you: this submission was already in the state you wanted to change it to."
                ),
            )
        elif self.is_allowed:
            self.do()
        else:
            self.do(force=True)
        url = self.request.GET.get("next")
        if url and url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            return redirect(url)
        return redirect(self.object.orga_urls.base)

    @context
    def next(self):
        return self.request.GET.get("next")


class SubmissionSpeakersAdd(SubmissionViewMixin, View):
    permission_required = "submission.edit_speaker_list"

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission = self.object
        email = request.POST.get("speaker")
        name = request.POST.get("name")
        speaker = None
        try:
            speaker = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            with suppress(Exception):
                speaker = create_user_as_orga(email, submission=submission, name=name)
        if not speaker:
            messages.error(request, _("Please provide a valid email address!"))
        else:
            if submission not in speaker.submissions.all():
                speaker.submissions.add(submission)
                submission.log_action(
                    "pretalx.submission.speakers.add", person=request.user, orga=True
                )
                messages.success(
                    request, _("The speaker has been added to the submission.")
                )
            else:
                messages.warning(
                    request, _("The speaker was already part of the submission.")
                )
            if not speaker.profiles.filter(event=request.event).exists():
                SpeakerProfile.objects.create(user=speaker, event=request.event)
        return redirect(submission.orga_urls.speakers)


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
                request, _("The speaker has been removed from the submission.")
            )
        else:
            messages.warning(request, _("The speaker was not part of this submission."))
        return redirect(submission.orga_urls.speakers)


class SubmissionSpeakers(SubmissionViewMixin, TemplateView):
    template_name = "orga/submission/speakers.html"
    permission_required = "orga.view_speakers"

    @context
    def speakers(self):
        submission = self.object
        return [
            {
                "id": speaker.id,
                "name": speaker.get_display_name(),
                "biography": speaker.profiles.get_or_create(event=submission.event)[
                    0
                ].biography,
                "other_submissions": speaker.submissions.filter(
                    event=submission.event
                ).exclude(code=submission.code),
            }
            for speaker in submission.speakers.all()
        ]

    @context
    def users(self):
        return User.objects.all()


class SubmissionContent(ActionFromUrl, SubmissionViewMixin, CreateOrUpdateView):
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
            queryset=submission.resources.all()
            if submission
            else Resource.objects.none(),
            prefix="resource",
        )

    @context
    def formset(self):
        return self._formset

    @cached_property
    def _questions_form(self):
        submission = self.get_object()
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
                change_data = {k: form.cleaned_data.get(k) for k in form.changed_data}
                change_data["id"] = form.instance.pk
                obj.log_action(
                    "pretalx.submission.resource.update", person=self.request.user
                )

        extra_forms = [
            form
            for form in self._formset.extra_forms
            if form.has_changed
            and not self._formset._should_delete_form(form)
            and form.instance.resource
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

    def get_permission_object(self):
        return self.object or self.request.event

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
            email = form.cleaned_data["speaker"]
            try:
                speaker = User.objects.get(email__iexact=email)  # TODO: send email!
                messages.success(
                    self.request,
                    _(
                        "The submission has been created; the speaker already had an account on this system."
                    ),
                )
            except User.DoesNotExist:
                speaker = create_user_as_orga(
                    email=email,
                    name=form.cleaned_data["speaker_name"],
                    submission=form.instance,
                )
                messages.success(
                    self.request,
                    _(
                        "The submission has been created and the speaker has been invited to add an account!"
                    ),
                )

            form.instance.speakers.add(speaker)
        else:
            formset_result = self.save_formset(form.instance)
            if not formset_result:
                return self.get(self.request, *self.args, **self.kwargs)
            messages.success(self.request, _("The submission has been updated!"))
        if form.has_changed():
            action = "pretalx.submission." + ("create" if created else "update")
            form.instance.log_action(action, person=self.request.user, orga=True)
            self.request.event.cache.set("rebuild_schedule_export", True, None)
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        return kwargs


class SubmissionList(EventPermissionRequired, Sortable, Filterable, ListView):
    model = Submission
    context_object_name = "submissions"
    template_name = "orga/submission/list.html"
    default_filters = {"code__icontains", "title__icontains"}
    filter_fields = ("submission_type", "state", "track")
    filter_form_class = SubmissionFilterForm
    sortable_fields = ("code", "title", "state", "is_featured")
    permission_required = "orga.view_submissions"
    paginate_by = 25

    def dispatch(self, *args, **kwargs):
        if self.request.user.has_perm("orga.view_speakers", self.request.event):
            self.default_filters.add("speakers__name__icontains")
        return super().dispatch(*args, **kwargs)

    @context
    def show_submission_types(self):
        return self.request.event.submission_types.all().count() > 1

    @context
    def show_tracks(self):
        return (
            self.request.event.settings.use_tracks
            and self.request.event.tracks.all().count() > 1
        )

    def get_queryset(self):
        qs = (
            Submission.all_objects.filter(event=self.request.event)
            .select_related("submission_type")
            .order_by("-id")
            .all()
        )
        qs = self.filter_queryset(qs)
        if "state" not in self.request.GET:
            qs = qs.exclude(state="deleted")
        qs = self.sort_queryset(qs)
        return qs.distinct()


class FeedbackList(SubmissionViewMixin, ListView):
    template_name = "orga/submission/feedback_list.html"
    context_object_name = "feedback"
    paginate_by = 25
    permission_required = "submission.view_feedback"

    def get_queryset(self):
        return self.object.feedback.all().order_by("pk")


class ToggleFeatured(SubmissionViewMixin, View):
    permission_required = "orga.change_submissions"

    def get_permission_object(self):
        return self.object or self.request.event

    def post(self, *args, **kwargs):
        self.object.is_featured = not self.object.is_featured
        self.object.save(update_fields=["is_featured"])
        return HttpResponse()


class SubmissionFeed(PermissionRequired, Feed):

    permission_required = "orga.view_submission"
    feed_type = feedgenerator.Atom1Feed

    def get_object(self, request, *args, **kwargs):
        return request.event

    def title(self, obj):
        return _("{name} submission feed").format(name=obj.name)

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
        return _("New {event} submission: {title}").format(
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
    def show_tracks(self):
        return (
            self.request.event.settings.use_tracks
            and self.request.event.tracks.all().count() > 1
        )

    @context
    def submission_timeline_data(self):
        data = Counter(
            timestamp.astimezone(self.request.event.tz).date()
            for timestamp in ActivityLog.objects.filter(
                event=self.request.event, action_type="pretalx.submission.create"
            ).values_list("timestamp", flat=True)
        )
        dates = data.keys()
        if len(dates) > 1:
            date_range = rrule.rrule(
                rrule.DAILY,
                count=(max(dates) - min(dates)).days + 1,
                dtstart=min(dates),
            )
            if len(data) > 1:
                return json.dumps(
                    [
                        {"x": date.isoformat(), "y": data.get(date.date(), 0)}
                        for date in date_range
                    ]
                )
        return ""

    @context
    @cached_property
    def submission_state_data(self):
        counter = Counter(
            submission.get_state_display()
            for submission in Submission.all_objects.filter(event=self.request.event)
        )
        return json.dumps(
            sorted(
                list(
                    {"label": label, "value": value} for label, value in counter.items()
                ),
                key=itemgetter("label"),
            )
        )

    @context
    def submission_type_data(self):
        counter = Counter(
            str(submission.submission_type)
            for submission in Submission.all_objects.filter(event=self.request.event)
        )
        return json.dumps(
            sorted(
                list(
                    {"label": label, "value": value} for label, value in counter.items()
                ),
                key=itemgetter("label"),
            )
        )

    @context
    def submission_track_data(self):
        if self.request.event.settings.use_tracks:
            counter = Counter(
                str(submission.track)
                for submission in Submission.all_objects.filter(
                    event=self.request.event
                )
            )
            return json.dumps(
                sorted(
                    list(
                        {"label": label, "value": value}
                        for label, value in counter.items()
                    ),
                    key=itemgetter("label"),
                )
            )
        return ""

    @context
    def talk_timeline_data(self):
        data = Counter(
            log.timestamp.astimezone(self.request.event.tz).date()
            for log in ActivityLog.objects.filter(
                event=self.request.event, action_type="pretalx.submission.create",
            )
            if getattr(log.content_object, "state", None)
            in [SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED]
        )
        dates = data.keys()
        if len(dates) > 1:
            date_range = rrule.rrule(
                rrule.DAILY,
                count=(max(dates) - min(dates)).days + 1,
                dtstart=min(dates),
            )
            if len(data) > 1:
                return json.dumps(
                    [
                        {"x": date.isoformat(), "y": data.get(date.date(), 0)}
                        for date in date_range
                    ]
                )
        return ""

    @context
    def talk_state_data(self):
        counter = Counter(
            submission.get_state_display()
            for submission in self.request.event.submissions.filter(
                state__in=[SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED]
            )
        )
        return json.dumps(
            sorted(
                list(
                    {"label": label, "value": value} for label, value in counter.items()
                ),
                key=itemgetter("label"),
            )
        )

    @context
    def talk_type_data(self):
        counter = Counter(
            str(submission.submission_type)
            for submission in self.request.event.submissions.filter(
                state__in=[SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED]
            )
        )
        return json.dumps(
            sorted(
                list(
                    {"label": label, "value": value} for label, value in counter.items()
                ),
                key=itemgetter("label"),
            )
        )

    @context
    def talk_track_data(self):
        if self.request.event.settings.use_tracks:
            counter = Counter(
                str(submission.track)
                for submission in self.request.event.submissions.filter(
                    state__in=[SubmissionStates.ACCEPTED, SubmissionStates.CONFIRMED]
                )
            )
            return json.dumps(
                sorted(
                    list(
                        {"label": label, "value": value}
                        for label, value in counter.items()
                    ),
                    key=itemgetter("label"),
                )
            )
        return ""


class AllFeedbacksList(EventPermissionRequired, ListView):
    model = Feedback
    context_object_name = "feedback"
    template_name = "orga/submission/feedbacks_list.html"

    permission_required = "orga.view_submissions"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Feedback.objects.order_by("-pk")
            .select_related("talk")
            .filter(talk__event=self.request.event)
        )
        return qs
