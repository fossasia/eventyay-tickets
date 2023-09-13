from csp.decorators import csp_update
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, FormView, ListView, View
from django_context_decorator import context

from pretalx.common.exceptions import SendMailException
from pretalx.common.mixins.views import (
    ActionFromUrl,
    EventPermissionRequired,
    Filterable,
    PaginationMixin,
    PermissionRequired,
    Sortable,
)
from pretalx.common.signals import register_data_exporters
from pretalx.common.views import CreateOrUpdateView
from pretalx.orga.forms.speaker import SpeakerExportForm
from pretalx.person.forms import (
    SpeakerFilterForm,
    SpeakerInformationForm,
    SpeakerProfileForm,
)
from pretalx.person.models import SpeakerInformation, SpeakerProfile, User
from pretalx.submission.forms import QuestionsForm
from pretalx.submission.models import Answer
from pretalx.submission.models.submission import SubmissionStates


def can_view_all_tracks(user, event):
    if user.is_administrator:
        return True
    user_teams = event.teams.filter(members__in=[user])
    return not all(team.limit_tracks.all().exists() for team in user_teams)


def get_review_tracks(user, event):
    tracks = []
    user_teams = event.teams.filter(members__in=[user])
    for team in user_teams:
        tracks += list(team.limit_tracks.all())
    return tracks


def get_speaker_profiles_for_user(user, event):
    users = event.submitters
    if not can_view_all_tracks(user, event):
        tracks = get_review_tracks(user, event)
        users = users.filter(submissions__track__in=tracks)
    return SpeakerProfile.objects.filter(event=event, user__in=users)


class SpeakerList(
    EventPermissionRequired, Sortable, Filterable, PaginationMixin, ListView
):
    model = SpeakerProfile
    template_name = "orga/speaker/list.html"
    context_object_name = "speakers"
    default_filters = ("user__email__icontains", "user__name__icontains")
    sortable_fields = ("user__email", "user__name")
    default_sort_field = "user__name"
    paginate_by = 25
    permission_required = "orga.view_speakers"

    @context
    def filter_form(self):
        return SpeakerFilterForm(self.request.event, self.request.GET)

    def get_queryset(self):
        qs = (
            get_speaker_profiles_for_user(self.request.user, self.request.event)
            .select_related("event", "user")
            .annotate(
                submission_count=Count(
                    "user__submissions",
                    filter=Q(user__submissions__event=self.request.event),
                ),
                accepted_submission_count=Count(
                    "user__submissions",
                    filter=Q(user__submissions__event=self.request.event)
                    & Q(user__submissions__state__in=["accepted", "confirmed"]),
                ),
            )
        )

        qs = self.filter_queryset(qs)
        if "role" in self.request.GET:
            if self.request.GET["role"] == "true":
                qs = qs.filter(
                    user__submissions__in=self.request.event.submissions.filter(
                        state__in=[
                            SubmissionStates.ACCEPTED,
                            SubmissionStates.CONFIRMED,
                        ]
                    )
                )
            elif self.request.GET["role"] == "false":
                qs = qs.exclude(
                    user__submissions__in=self.request.event.submissions.filter(
                        state__in=[
                            SubmissionStates.ACCEPTED,
                            SubmissionStates.CONFIRMED,
                        ]
                    )
                )

        question = self.request.GET.get("question")
        unanswered = self.request.GET.get("unanswered")
        answer = self.request.GET.get("answer")
        option = self.request.GET.get("answer__options")
        if question and (answer or option):
            if option:
                answers = Answer.objects.filter(
                    person_id=OuterRef("user_id"),
                    question_id=question,
                    options__pk=option,
                )
            else:
                answers = Answer.objects.filter(
                    person_id=OuterRef("user_id"),
                    question_id=question,
                    answer__exact=answer,
                )
            qs = qs.annotate(has_answer=Exists(answers)).filter(has_answer=True)
        elif question and unanswered:
            answers = Answer.objects.filter(
                question_id=question, person_id=OuterRef("user_id")
            )
            qs = qs.annotate(has_answer=Exists(answers)).filter(has_answer=False)
        qs = qs.order_by("id").distinct()
        qs = self.sort_queryset(qs)
        return qs


class SpeakerViewMixin(PermissionRequired):
    def get_object(self):
        return get_object_or_404(
            User.objects.filter(
                profiles__in=get_speaker_profiles_for_user(
                    self.request.user, self.request.event
                )
            )
            .order_by("id")
            .distinct(),
            code=self.kwargs["code"],
        )

    @cached_property
    def object(self):
        return self.get_object()

    @context
    @cached_property
    def profile(self):
        return self.object.event_profile(self.request.event)

    def get_permission_object(self):
        return self.profile

    @cached_property
    def permission_object(self):
        return self.get_permission_object()


@method_decorator(csp_update(IMG_SRC="https://www.gravatar.com"), name="dispatch")
class SpeakerDetail(SpeakerViewMixin, ActionFromUrl, CreateOrUpdateView):
    template_name = "orga/speaker/form.html"
    form_class = SpeakerProfileForm
    model = User
    permission_required = "orga.view_speaker"
    write_permission_required = "orga.change_speaker"

    def get_success_url(self) -> str:
        return self.profile.orga_urls.base

    @context
    @cached_property
    def submissions(self, **kwargs):
        qs = self.request.event.submissions.filter(speakers__in=[self.object])
        if not can_view_all_tracks(self.request.user, self.request.event):
            tracks = get_review_tracks(self.request.user, self.request.event)
            qs = qs.filter(track__in=tracks)
        return qs

    @context
    @cached_property
    def mails(self):
        return self.object.mails.filter(
            sent__isnull=False, event=self.request.event
        ).order_by("-sent")

    @context
    @cached_property
    def questions_form(self):
        speaker = self.get_object()
        return QuestionsForm(
            self.request.POST if self.request.method == "POST" else None,
            files=self.request.FILES if self.request.method == "POST" else None,
            target="speaker",
            speaker=speaker,
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

    @transaction.atomic()
    def form_valid(self, form):
        result = super().form_valid(form)
        if not self.questions_form.is_valid():
            return self.get(self.request, *self.args, **self.kwargs)
        self.questions_form.save()
        if form.has_changed():
            form.instance.log_action(
                "pretalx.user.profile.update", person=self.request.user, orga=True
            )
        if form.has_changed() or self.questions_form.has_changed():
            self.request.event.cache.set("rebuild_schedule_export", True, None)
        messages.success(self.request, "The speaker profile has been updated.")
        return result

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"event": self.request.event, "user": self.object})
        return kwargs


class SpeakerPasswordReset(SpeakerViewMixin, DetailView):
    permission_required = "orga.change_speaker"
    template_name = "orga/speaker/reset_password.html"
    model = User
    context_object_name = "speaker"

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        try:
            with transaction.atomic():
                user.reset_password(
                    event=getattr(self.request, "event", None),
                    user=self.request.user,
                    orga=False,
                )
                messages.success(
                    self.request, _("The password was reset and the user was notified.")
                )
        except SendMailException:  # pragma: no cover
            messages.error(
                self.request,
                _(
                    "The password reset email could not be sent, so the password was not reset."
                ),
            )
        return redirect(user.event_profile(self.request.event).orga_urls.base)


class SpeakerToggleArrived(SpeakerViewMixin, View):
    permission_required = "orga.change_speaker"

    def dispatch(self, request, event, code):
        self.profile.has_arrived = not self.profile.has_arrived
        self.profile.save()
        action = (
            "pretalx.speaker.arrived"
            if self.profile.has_arrived
            else "pretalx.speaker.unarrived"
        )
        self.object.log_action(
            action,
            data={"event": self.request.event.slug},
            person=self.request.user,
            orga=True,
        )
        if request.GET.get("from") == "list":
            return redirect(
                reverse("orga:speakers.list", kwargs={"event": self.kwargs["event"]})
            )
        return redirect(self.profile.orga_urls.base)


class InformationList(EventPermissionRequired, PaginationMixin, ListView):
    queryset = SpeakerInformation.objects.none()
    template_name = "orga/speaker/information_list.html"
    context_object_name = "information"
    permission_required = "orga.view_information"

    def get_queryset(self):
        return self.request.event.information.all().order_by("pk")


class InformationDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    template_name = "orga/speaker/information_form.html"
    form_class = SpeakerInformationForm
    model = SpeakerInformation
    permission_required = "orga.view_information"
    write_permission_required = "orga.change_information"

    def get_permission_object(self):
        return self.get_object() or self.request.event

    def get_object(self):
        if "pk" in self.kwargs:
            return self.request.event.information.filter(pk=self.kwargs["pk"]).first()
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.pop("read_only", None)
        kwargs["event"] = self.request.event
        return kwargs

    def get_success_url(self):
        return self.request.event.orga_urls.information


class InformationDelete(PermissionRequired, DetailView):
    model = SpeakerInformation
    permission_required = "orga.change_information"
    template_name = "orga/speaker/information_delete.html"

    def get_queryset(self):
        return self.request.event.information.all()

    def post(self, request, *args, **kwargs):
        information = self.get_object()
        information.delete()
        messages.success(request, _("The information has been deleted."))
        return redirect(request.event.orga_urls.information)


class SpeakerExport(EventPermissionRequired, FormView):
    permission_required = "orga.view_speakers"
    template_name = "orga/speaker/export.html"
    form_class = SpeakerExportForm

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["event"] = self.request.event
        return result

    @context
    def exporters(self):
        return list(
            exporter(self.request.event)
            for _, exporter in register_data_exporters.send(self.request.event)
            if exporter.group == "speaker"
        )

    def form_valid(self, form):
        result = form.export_data()
        if not result:
            messages.success(self.request, _("No data to be exported"))
            return redirect(self.request.path)
        return result
