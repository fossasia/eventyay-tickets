from csp.decorators import csp_update
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, ListView, View
from django_context_decorator import context

from pretalx.common.exceptions import SendMailException
from pretalx.common.mixins.views import (
    ActionFromUrl,
    EventPermissionRequired,
    Filterable,
    PermissionRequired,
    Sortable,
)
from pretalx.common.views import CreateOrUpdateView
from pretalx.person.forms import (
    SpeakerFilterForm,
    SpeakerInformationForm,
    SpeakerProfileForm,
)
from pretalx.person.models import SpeakerInformation, SpeakerProfile, User
from pretalx.submission.forms import QuestionsForm
from pretalx.submission.models.submission import Submission, SubmissionStates


class SpeakerList(EventPermissionRequired, Sortable, Filterable, ListView):
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
        return SpeakerFilterForm(self.request.GET)

    def get_queryset(self):
        qs = SpeakerProfile.objects.filter(
            event=self.request.event, user__in=self.request.event.submitters
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

        qs = qs.order_by("id").distinct()
        qs = self.sort_queryset(qs)
        return qs


@method_decorator(csp_update(IMG_SRC="https://www.gravatar.com"), name="dispatch")
class SpeakerDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    template_name = "orga/speaker/form.html"
    form_class = SpeakerProfileForm
    model = User
    permission_required = "orga.view_speaker"
    write_permission_required = "orga.change_speaker"

    def get_object(self):
        return get_object_or_404(
            User.objects.filter(
                submissions__in=Submission.all_objects.filter(event=self.request.event)
            )
            .order_by("id")
            .distinct(),
            pk=self.kwargs["pk"],
        )

    @cached_property
    def object(self):
        return self.get_object()

    def get_permission_object(self):
        return self.object.event_profile(self.request.event)

    @cached_property
    def permission_object(self):
        return self.get_permission_object()

    def get_success_url(self) -> str:
        return reverse(
            "orga:speakers.view",
            kwargs={"event": self.request.event.slug, "pk": self.kwargs["pk"]},
        )

    @context
    def submissions(self, **kwargs):
        return self.request.event.submissions.filter(speakers__in=[self.object])

    @context
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
        self.questions_form.speaker = self.get_object()
        if not self.questions_form.is_valid():
            return self.get(self.request, *self.args, **self.kwargs)
        self.questions_form.save()
        if form.has_changed():
            self.get_object().event_profile(self.request.event).log_action(
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


class SpeakerPasswordReset(EventPermissionRequired, DetailView):
    permission_required = "orga.change_speaker"
    template_name = "orga/speaker/reset_password.html"
    model = User
    context_object_name = "speaker"

    @context
    def profile(self):
        return self.get_object().event_profile(self.request.event)

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


class SpeakerToggleArrived(PermissionRequired, View):
    permission_required = "orga.change_speaker"

    def get_object(self):
        return get_object_or_404(
            SpeakerProfile, event=self.request.event, user_id=self.kwargs["pk"]
        )

    @cached_property
    def object(self):
        return self.get_object()

    def dispatch(self, request, event, pk):
        profile = self.object
        profile.has_arrived = not profile.has_arrived
        profile.save()
        action = (
            "pretalx.speaker.arrived"
            if profile.has_arrived
            else "pretalx.speaker.unarrived"
        )
        profile.user.log_action(
            action,
            data={"event": self.request.event.slug},
            person=self.request.user,
            orga=True,
        )
        if request.GET.get("from") == "list":
            return redirect(
                reverse("orga:speakers.list", kwargs={"event": self.kwargs["event"]})
            )
        return redirect(reverse("orga:speakers.view", kwargs=self.kwargs))


class InformationList(EventPermissionRequired, ListView):
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
        return kwargs

    def form_valid(self, form):
        if not getattr(form.instance, "event", None):
            form.instance.event = self.request.event
        return super().form_valid(form)

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
