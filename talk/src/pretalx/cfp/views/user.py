import logging
import textwrap
import urllib

from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.forms.models import BaseModelFormSet, inlineformset_factory
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from django.views.generic import (
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)
from django_context_decorator import context

from pretalx.cfp.forms.submissions import SubmissionInvitationForm
from pretalx.cfp.views.event import LoggedInEventPageMixin
from pretalx.common.exceptions import SendMailException
from pretalx.common.forms.fields import SizeFileInput
from pretalx.common.image import gravatar_csp
from pretalx.common.middleware.event import get_login_redirect
from pretalx.common.text.phrases import phrases
from pretalx.common.views import is_form_bound
from pretalx.person.forms import LoginInfoForm, SpeakerProfileForm
from pretalx.person.rules import can_view_information
from pretalx.schedule.forms import AvailabilitiesFormMixin
from pretalx.submission.forms import InfoForm, QuestionsForm, ResourceForm
from pretalx.submission.models import Resource, Submission, SubmissionStates

logger = logging.getLogger(__name__)


@method_decorator(gravatar_csp(), name="dispatch")
class ProfileView(LoggedInEventPageMixin, TemplateView):
    template_name = "cfp/event/user_profile.html"

    @context
    @cached_property
    def login_form(self):
        return LoginInfoForm(
            user=self.request.user,
            data=self.request.POST if is_form_bound(self.request, "login") else None,
        )

    @context
    @cached_property
    def profile_form(self):
        bind = is_form_bound(self.request, "profile")
        cfp_flow_config = self.request.event.cfp_flow.config
        try:
            # TODO: There may be a mismatch somewhere else between how the config was saved and how it is loaded.
            # We should use Pydantic model for saving and loading, to make sure the data is consistent.
            field_configuration = cfp_flow_config["steps"]["profile"]["fields"]
        except KeyError:
            field_configuration = None
        return SpeakerProfileForm(
            user=self.request.user,
            event=self.request.event,
            read_only=False,
            with_email=False,
            field_configuration=field_configuration,
            data=self.request.POST if bind else None,
            files=self.request.FILES if bind else None,
        )

    @context
    @cached_property
    def questions_form(self):
        bind = is_form_bound(self.request, "questions")
        return QuestionsForm(
            data=self.request.POST if bind else None,
            files=self.request.FILES if bind else None,
            speaker=self.request.user,
            event=self.request.event,
            target="speaker",
        )

    @context
    def questions_exist(self):
        return self.request.event.questions.filter(target="speaker").exists()

    def post(self, request, *args, **kwargs):
        if self.login_form.is_bound and self.login_form.is_valid():
            self.login_form.save()
            request.user.log_action("pretalx.user.password.update")
        elif self.profile_form.is_bound and self.profile_form.is_valid():
            self.profile_form.save()
            profile = self.request.user.profiles.get_or_create(
                event=self.request.event
            )[0]
            profile.log_action("pretalx.user.profile.update", person=request.user)
            if self.profile_form.has_changed():
                self.request.event.cache.set("rebuild_schedule_export", True, None)
        elif self.questions_form.is_bound and self.questions_form.is_valid():
            self.questions_form.save()
            if self.questions_form.has_changed():
                self.request.event.cache.set("rebuild_schedule_export", True, None)
        else:
            return super().get(request, *args, **kwargs)

        messages.success(self.request, phrases.base.saved)
        return redirect("cfp:event.user.view", event=self.request.event.slug)


class SubmissionViewMixin:
    permission_required = "submission.update_submission"

    def has_permission(self):
        return super().has_permission() or self.request.user.has_perm(
            "submission.orga_list_submission", self.request.event
        )

    def dispatch(self, request, *args, **kwargs):
        if self.request.user not in self.object.speakers.all():
            # User has permission to see permission, but not to see this particular
            # page, so we redirect them to the organiser page
            return redirect(self.object.orga_urls.base)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):

        return get_object_or_404(
            Submission.all_objects.filter(event=self.request.event)
            .exclude(state=SubmissionStates.DELETED)
            .prefetch_related("answers", "answers__options", "speakers"),
            code__iexact=self.kwargs["code"],
        )

    @context
    @cached_property
    def object(self):
        return self.get_object()

    @context
    @cached_property
    def submission(self, **kwargs):
        return self.get_object()


class SubmissionsListView(LoggedInEventPageMixin, ListView):
    template_name = "cfp/event/user_submissions.html"
    context_object_name = "submissions"

    @context
    def information(self):
        return [
            info
            for info in self.request.event.information.all()
            if can_view_information(self.request.user, info)
        ]

    @context
    def drafts(self):
        return Submission.all_objects.filter(
            event=self.request.event,
            speakers__in=[self.request.user],
            state=SubmissionStates.DRAFT,
        )

    def get_queryset(self):
        return self.request.event.submissions.filter(speakers__in=[self.request.user])


class SubmissionsWithdrawView(LoggedInEventPageMixin, SubmissionViewMixin, DetailView):
    template_name = "cfp/event/user_submission_withdraw.html"
    model = Submission
    context_object_name = "submission"
    permission_required = "submission.is_speaker_submission"

    def get_permission_object(self):
        return self.get_object()

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        if self.request.user.has_perm("submission.withdraw_submission", obj):
            if obj.state == SubmissionStates.ACCEPTED:
                with override(obj.event.locale):
                    obj.event.send_orga_mail(
                        str(
                            _(
                                textwrap.dedent(
                                    """
                        Hi,

                        this is your content system at {event_dashboard}.
                        Your accepted talk “{title}” by {speakers} was just withdrawn by {user}.
                        You can find details at {url}.

                        Best regards,
                        pretalx
                        """
                                )
                            )
                        ).format(
                            title=obj.title,
                            speakers=obj.display_speaker_names,
                            user=request.user.get_display_name(),
                            event_dashboard=request.event.orga_urls.base.full(),
                            url=obj.orga_urls.edit.full(),
                        )
                    )
            obj.withdraw(person=request.user)
            messages.success(self.request, phrases.cfp.submission_withdrawn)
        else:
            messages.error(self.request, phrases.cfp.submission_not_withdrawn)
        return redirect("cfp:event.user.submissions", event=self.request.event.slug)


class SubmissionConfirmView(LoggedInEventPageMixin, SubmissionViewMixin, FormView):
    template_name = "cfp/event/user_submission_confirm.html"
    form_class = AvailabilitiesFormMixin

    def get_object(self):
        return get_object_or_404(
            self.request.event.submissions, code__iexact=self.kwargs.get("code")
        )

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_anonymous:
            return get_login_redirect(request)
        if not request.user.has_perm(
            "submission.is_speaker_submission", self.submission
        ):
            self.template_name = "cfp/event/user_submission_confirm_error.html"
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def speaker_profile(self):
        return self.request.user.event_profile(self.request.event)

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["instance"] = self.speaker_profile
        result["event"] = self.request.event
        result["limit_to_rooms"] = True
        return result

    def get_form(self):
        form = super().get_form()
        if not self.request.event.cfp.request_availabilities:
            form.fields.pop("availabilities")
        else:
            form.fields["availabilities"].required = (
                self.request.event.cfp.require_availabilities
            )
        return form

    def form_valid(self, form):
        submission = self.submission
        form.save()
        if self.request.user.has_perm("submission.confirm_submission", submission):
            submission.confirm(person=self.request.user)
            messages.success(self.request, phrases.cfp.submission_confirmed)
        elif submission.state == SubmissionStates.CONFIRMED:
            messages.success(self.request, phrases.cfp.submission_was_confirmed)
        else:
            messages.error(self.request, phrases.cfp.submission_not_confirmed)
        return redirect("cfp:event.user.submissions", event=self.request.event.slug)


class SubmissionDraftDiscardView(
    LoggedInEventPageMixin, SubmissionViewMixin, TemplateView
):
    template_name = "cfp/event/user_submission_discard.html"
    form_class = AvailabilitiesFormMixin

    def get_object(self):
        submission = super().get_object()
        if submission.state != SubmissionStates.DRAFT:
            raise Http404()
        return submission

    def post(self, request, *args, **kwargs):
        self.submission.delete()
        messages.success(self.request, _("Your draft was discarded."))
        return redirect("cfp:event.user.submissions", event=self.request.event.slug)


class SubmissionsEditView(LoggedInEventPageMixin, SubmissionViewMixin, UpdateView):
    template_name = "cfp/event/user_submission_edit.html"
    model = Submission
    form_class = InfoForm
    context_object_name = "submission"
    permission_required = "submission.view_submission"
    write_permission_required = "submission.update_submission"

    def get_permission_object(self):
        return self.object

    @context
    def size_warning(self):
        return SizeFileInput.get_size_warning()

    @context
    @cached_property
    def formset(self):
        formset_class = inlineformset_factory(
            Submission,
            Resource,
            form=ResourceForm,
            formset=BaseModelFormSet,
            can_delete=True,
            extra=0,
        )
        submission = self.object
        return formset_class(
            self.request.POST if self.request.method == "POST" else None,
            files=self.request.FILES if self.request.method == "POST" else None,
            queryset=(
                submission.resources.all() if submission else Resource.objects.none()
            ),
            prefix="resource",
        )

    def save_formset(self, obj):
        if not self.formset.is_valid():
            return False

        for form in self.formset.initial_forms:
            if form in self.formset.deleted_forms:
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
            for form in self.formset.extra_forms
            if form.has_changed
            and not self.formset._should_delete_form(form)
            and form.is_valid()
        ]
        for form in extra_forms:
            form.instance.submission = obj
            form.save()
            obj.log_action(
                "pretalx.submission.resource.create",
                person=self.request.user,
                data={"id": form.instance.pk},
            )

        return True

    @context
    @cached_property
    def qform(self):
        return QuestionsForm(
            data=self.request.POST if self.request.method == "POST" else None,
            files=self.request.FILES if self.request.method == "POST" else None,
            submission=self.object,
            target="submission",
            event=self.request.event,
            readonly=not self.can_edit,
        )

    @cached_property
    def object(self):
        return self.get_object()

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid() and self.qform.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    @context
    @cached_property
    def can_edit(self):
        return self.object.editable

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        kwargs["field_configuration"] = (
            self.request.event.cfp_flow.config.get("steps", {})
            .get("info", {})
            .get("fields")
        )
        kwargs["readonly"] = not self.can_edit
        # At this stage, new speakers can be added via the dedicated form
        kwargs["remove_additional_speaker"] = True
        return kwargs

    def form_valid(self, form):
        if self.can_edit:
            form.save()
            self.qform.save()
            result = self.save_formset(form.instance)
            if not result:
                return self.get(self.request, *self.args, **self.kwargs)
            if form.has_changed():
                if form.instance.pk and "duration" in form.changed_data:
                    form.instance.update_duration()
                if form.instance.pk and "track" in form.changed_data:
                    form.instance.update_review_scores()
                if form.instance.pk and "additional_speaker" in form.changed_data:
                    try:
                        form.instance.send_invite(
                            to=[form.cleaned_data.get("additional_speaker")],
                            _from=self.request.user,
                        )
                    except SendMailException as exception:
                        logger.warning("Failed to send email with error: %s", exception)
                        messages.warning(
                            self.request, phrases.cfp.submission_email_fail
                        )
                form.instance.log_action(
                    "pretalx.submission.update", person=self.request.user
                )
                self.request.event.cache.set("rebuild_schedule_export", True, None)
            if (
                form.instance.state == SubmissionStates.DRAFT
                and self.request.method == "POST"
                and self.request.POST.get("action", "submit") == "dedraft"
            ):
                form.instance.make_submitted(person=self.request.user)
                form.instance.log_action(
                    "pretalx.submission.create", person=self.request.user
                )
                messages.success(self.request, _("Your proposal has been submitted."))
                return redirect(self.request.event.urls.user_submissions)
            else:
                messages.success(self.request, phrases.base.saved)
        else:
            messages.error(self.request, phrases.cfp.submission_uneditable)
        return redirect(self.object.urls.user_base)


class DeleteAccountView(LoggedInEventPageMixin, View):
    @staticmethod
    def post(request, event):
        if request.POST.get("really"):
            request.user.deactivate()
            logout(request)
            messages.success(request, _("Your account has now been deleted."))
            return redirect(request.event.urls.base)
        messages.error(request, _("Are you really sure? Please tick the box"))
        return redirect(request.event.urls.user + "?really")


class SubmissionInviteView(LoggedInEventPageMixin, SubmissionViewMixin, FormView):
    form_class = SubmissionInvitationForm
    template_name = "cfp/event/user_submission_invitation.html"
    permission_required = "submission.add_speaker_submission"

    def get_permission_object(self):
        return self.get_object()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["submission"] = self.submission
        kwargs["speaker"] = self.request.user
        if "email" in self.request.GET and self.request.method != "POST":
            initial = kwargs.get("initial", {})
            initial["speaker"] = urllib.parse.unquote(self.request.GET["email"])
            kwargs["initial"] = initial

            try:
                validate_email(initial["speaker"])
            except ValidationError:
                messages.warning(self.request, phrases.cfp.invite_invalid_email)
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, phrases.cfp.invite_sent)
        self.submission.log_action(
            "pretalx.submission.speakers.invite", person=self.request.user
        )
        return super().form_valid(form)

    def get_success_url(self):
        return self.submission.urls.user_base


class SubmissionInviteAcceptView(LoggedInEventPageMixin, DetailView):
    template_name = "cfp/event/invitation.html"
    context_object_name = "submission"

    def get_object(self, queryset=None):
        return get_object_or_404(
            Submission,
            code__iexact=self.kwargs["code"],
            invitation_token__iexact=self.kwargs["invitation"],
        )

    @context
    @cached_property
    def can_accept_invite(self):
        return self.request.user.has_perm(
            "submission.add_speaker_submission", self.get_object()
        )

    def post(self, request, *args, **kwargs):
        if not self.can_accept_invite:
            messages.error(self.request, _("You cannot accept this invitation."))
            return redirect(self.request.event.urls.user)
        submission = self.get_object()
        submission.speakers.add(self.request.user)
        submission.log_action(
            "pretalx.submission.speakers.add", person=self.request.user
        )
        submission.save()
        messages.success(self.request, phrases.cfp.invite_accepted)
        return redirect("cfp:event.user.view", event=self.request.event.slug)


class MailListView(LoggedInEventPageMixin, TemplateView):
    template_name = "cfp/event/user_mails.html"

    @context
    def mails(self):
        return self.request.user.mails.filter(sent__isnull=False).order_by("-sent")
