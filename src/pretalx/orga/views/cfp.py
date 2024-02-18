import json
from collections import defaultdict

from csp.decorators import csp_update
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.forms.models import inlineformset_factory
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, ListView, TemplateView, UpdateView, View
from django_context_decorator import context

from pretalx.cfp.flow import CfPFlow
from pretalx.common.forms import I18nFormSet
from pretalx.common.mixins.views import (
    ActionFromUrl,
    EventPermissionRequired,
    PaginationMixin,
    PermissionRequired,
)
from pretalx.common.utils import I18nStrJSONEncoder
from pretalx.common.views import CreateOrUpdateView, OrderModelView
from pretalx.orga.forms import CfPForm, QuestionForm, SubmissionTypeForm, TrackForm
from pretalx.orga.forms.cfp import (
    AccessCodeSendForm,
    AnswerOptionForm,
    CfPSettingsForm,
    QuestionFilterForm,
    ReminderFilterForm,
    SubmitterAccessCodeForm,
)
from pretalx.submission.models import (
    AnswerOption,
    CfP,
    Question,
    QuestionTarget,
    SubmissionType,
    SubmitterAccessCode,
    Track,
)


class CfPTextDetail(PermissionRequired, ActionFromUrl, UpdateView):
    form_class = CfPForm
    model = CfP
    template_name = "orga/cfp/text.html"
    permission_required = "orga.edit_cfp"
    write_permission_required = "orga.edit_cfp"

    @context
    @cached_property
    def sform(self):
        return CfPSettingsForm(
            read_only=(self.action == "view"),
            locales=self.request.event.locales,
            obj=self.request.event,
            data=self.request.POST if self.request.method == "POST" else None,
            prefix="settings",
        )

    @context
    @cached_property
    def different_deadlines(self):
        deadlines = defaultdict(list)
        for session_type in self.request.event.submission_types.filter(
            deadline__isnull=False
        ):
            deadlines[session_type.deadline].append(session_type)
        deadlines.pop(self.request.event.cfp.deadline, None)
        if len(deadlines):
            return dict(deadlines)

    def get_object(self):
        return self.request.event.cfp

    def get_success_url(self) -> str:
        return self.object.urls.text

    @transaction.atomic
    def form_valid(self, form):
        if not self.sform.is_valid():
            messages.error(self.request, _("We had trouble saving your input."))
            return self.form_invalid(form)
        messages.success(self.request, "The CfP update has been saved.")
        form.instance.event = self.request.event
        result = super().form_valid(form)
        if form.has_changed():
            form.instance.log_action(
                "pretalx.cfp.update", person=self.request.user, orga=True
            )
        self.sform.save()
        return result


class CfPQuestionList(EventPermissionRequired, TemplateView):
    template_name = "orga/cfp/question_view.html"
    permission_required = "orga.view_question"

    @context
    def questions(self):
        return Question.all_objects.filter(event=self.request.event).annotate(
            answer_count=Count("answers")
        )


class CfPQuestionDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = Question
    form_class = QuestionForm
    permission_required = "orga.edit_question"
    write_permission_required = "orga.edit_question"

    def get_template_names(self):
        action = self.request.path.lstrip("/").rpartition("/")[2]
        if action in ("edit", "new"):
            return "orga/cfp/question_form.html"
        return "orga/cfp/question_detail.html"

    @property
    def permission_object(self):
        return self.object or self.request.event

    def get_permission_object(self):
        return self.permission_object

    def get_object(self) -> Question:
        return Question.all_objects.filter(
            event=self.request.event, pk=self.kwargs.get("pk")
        ).first()

    @cached_property
    def object(self):
        return self.get_object()

    @context
    @cached_property
    def question(self):
        return self.object

    @context
    @cached_property
    def base_search_url(self):
        if not self.question or self.question.target == "reviewer":
            return
        role = self.request.GET.get("role") or ""
        track = self.request.GET.get("track") or ""
        submission_type = self.request.GET.get("submission_type") or ""
        if self.question.target == "submission":
            url = self.request.event.orga_urls.submissions + "?"
            if role == "accepted":
                url = f"{url}state=accepted&state=confirmed&"
            elif role == "confirmed":
                url = f"{url}state=confirmed&"
            if track:
                url = f"{url}track={track}&"
            if submission_type:
                url = f"{url}submission_type={submission_type}&"
        else:
            url = self.request.event.orga_urls.speakers + "?"
        url = f"{url}&question={self.question.id}&"
        return url

    @context
    @cached_property
    def formset(self):
        formset_class = inlineformset_factory(
            Question,
            AnswerOption,
            form=AnswerOptionForm,
            formset=I18nFormSet,
            can_delete=True,
            extra=0,
        )
        return formset_class(
            self.request.POST if self.request.method == "POST" else None,
            queryset=(
                AnswerOption.objects.filter(question=self.object)
                if self.object
                else AnswerOption.objects.none()
            ),
            event=self.request.event,
        )

    def save_formset(self, obj):
        if not self.formset.is_valid():
            return False
        for form in self.formset.initial_forms:
            if form in self.formset.deleted_forms:
                if not form.instance.pk:
                    continue
                obj.log_action(
                    "pretalx.question.option.delete",
                    person=self.request.user,
                    orga=True,
                    data={"id": form.instance.pk},
                )
                form.instance.delete()
                form.instance.pk = None
            elif form.has_changed():
                form.instance.question = obj
                form.save()
                change_data = {k: form.cleaned_data.get(k) for k in form.changed_data}
                change_data["id"] = form.instance.pk
                obj.log_action(
                    "pretalx.question.option.update",
                    person=self.request.user,
                    orga=True,
                    data=change_data,
                )

        extra_forms = [
            form
            for form in self.formset.extra_forms
            if form.has_changed and not self.formset._should_delete_form(form)
        ]
        for form in extra_forms:
            form.instance.question = obj
            form.save()
            change_data = {k: form.cleaned_data.get(k) for k in form.changed_data}
            change_data["id"] = form.instance.pk
            obj.log_action(
                "pretalx.question.option.create",
                person=self.request.user,
                orga=True,
                data=change_data,
            )

        return True

    @context
    @cached_property
    def filter_form(self):
        return QuestionFilterForm(self.request.GET, event=self.request.event)

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        question = self.object
        if not question or not self.filter_form.is_valid():
            return result
        result.update(self.filter_form.get_question_information(question))
        result["grouped_answers_json"] = json.dumps(
            list(result["grouped_answers"]), cls=I18nStrJSONEncoder
        )
        return result

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event"] = self.request.event
        if not self.object:
            initial = kwargs["initial"] or {}
            initial["target"] = self.request.GET.get("type")
            kwargs["initial"] = initial
        return kwargs

    def get_success_url(self) -> str:
        if "pk" in self.kwargs and self.object:
            return self.object.urls.base
        return self.request.event.cfp.urls.questions

    @transaction.atomic
    def form_valid(self, form):
        form.instance.event = self.request.event
        self.instance = form.instance
        # Last-ditch validation: We can't allow both a question option upload
        # AND changes in the question option formset.
        if form.cleaned_data.get("variant") in ("choices", "multiple_choice"):
            changed_options = [
                form.changed_data for form in self.formset if form.has_changed()
            ]
            if form.cleaned_data.get("options") and changed_options:
                messages.error(
                    self.request,
                    _(
                        "You cannot change the question options and upload a question option file at the same time."
                    ),
                )
                return self.form_invalid(form)
        result = super().form_valid(form)
        if form.cleaned_data.get("variant") in (
            "choices",
            "multiple_choice",
        ) and not form.cleaned_data.get("options"):
            formset = self.save_formset(self.instance)
            if not formset:
                return self.get(self.request, *self.args, **self.kwargs)
        if form.has_changed():
            action = "pretalx.question." + (
                "update" if "pk" in self.kwargs else "create"
            )
            form.instance.log_action(action, person=self.request.user, orga=True)
        messages.success(self.request, "The question has been saved.")
        return result


class CfPQuestionDelete(PermissionRequired, DetailView):
    permission_required = "orga.remove_question"
    template_name = "orga/cfp/question_delete.html"

    def get_object(self) -> Question:
        return get_object_or_404(
            Question.all_objects, event=self.request.event, pk=self.kwargs.get("pk")
        )

    def post(self, request, *args, **kwargs):
        question = self.get_object()

        try:
            with transaction.atomic():
                question.options.all().delete()
                question.logged_actions().delete()
                question.delete()
                request.event.log_action(
                    "pretalx.question.delete", person=self.request.user, orga=True
                )
                messages.success(request, _("The question has been deleted."))
        except ProtectedError:
            question.active = False
            question.save()
            messages.error(
                request,
                _(
                    "You cannot delete a question that has already been answered. We have deactivated the question instead."
                ),
            )
        return redirect(self.request.event.cfp.urls.questions)


class QuestionOrderView(OrderModelView):
    permission_required = "orga.edit_question"
    model = Question

    def get_success_url(self):
        return self.request.event.cfp.urls.questions


class CfPQuestionToggle(PermissionRequired, View):
    permission_required = "orga.edit_question"

    def get_object(self) -> Question:
        return Question.all_objects.filter(
            event=self.request.event, pk=self.kwargs.get("pk")
        ).first()

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        question = self.get_object()

        question.active = not question.active
        question.save(update_fields=["active"])
        return redirect(question.urls.base)


class CfPQuestionRemind(EventPermissionRequired, TemplateView):
    template_name = "orga/cfp/question_remind.html"
    permission_required = "orga.view_question"

    @context
    @cached_property
    def filter_form(self):
        data = None if self.request.method == "GET" else self.request.POST
        return ReminderFilterForm(data, event=self.request.event)

    @staticmethod
    def get_missing_answers(*, questions, person, submissions):
        missing = []
        submissions = submissions.filter(speakers__in=[person])
        for question in questions:
            if question.target == QuestionTarget.SUBMISSION:
                for submission in submissions:
                    answer = question.answers.filter(submission=submission).first()
                    if not answer or not answer.is_answered:
                        missing.append(question)
                        continue
            elif question.target == QuestionTarget.SPEAKER:
                answer = question.answers.filter(person=person).first()
                if not answer or not answer.is_answered:
                    missing.append(question)
        return missing

    def post(self, request, *args, **kwargs):
        if not self.filter_form.is_valid():
            messages.error(request, _("Could not send mails, error in configuration."))
            return redirect(request.path)
        if not getattr(request.event, "question_template", None):
            request.event.build_initial_data()
        submissions = self.filter_form.get_submissions()
        people = request.event.submitters.filter(submissions__in=submissions)
        questions = (
            self.filter_form.cleaned_data["questions"]
            or self.filter_form.get_question_queryset()
        )
        data = {
            "url": request.event.urls.user_submissions.full(),
        }
        for person in people:
            missing = self.get_missing_answers(
                questions=questions, person=person, submissions=submissions
            )
            if missing:
                data["questions"] = "\n".join(
                    f"- {question.question}" for question in missing
                )
                request.event.question_template.to_mail(
                    person,
                    event=request.event,
                    context=data,
                    context_kwargs={"user": person},
                )
        return redirect(request.event.orga_urls.outbox)


class SubmissionTypeList(EventPermissionRequired, PaginationMixin, ListView):
    template_name = "orga/cfp/submission_type_view.html"
    context_object_name = "types"
    permission_required = "orga.view_submission_type"

    def get_queryset(self):
        return self.request.event.submission_types.all().order_by("default_duration")


class SubmissionTypeDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = SubmissionType
    form_class = SubmissionTypeForm
    template_name = "orga/cfp/submission_type_form.html"
    permission_required = "orga.edit_submission_type"
    write_permission_required = "orga.edit_submission_type"

    def get_success_url(self) -> str:
        return self.request.event.cfp.urls.types

    def get_object(self):
        return self.request.event.submission_types.filter(
            pk=self.kwargs.get("pk")
        ).first()

    def get_permission_object(self):
        return self.get_object() or self.request.event

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["event"] = self.request.event
        return result

    def form_valid(self, form):
        messages.success(self.request, "The Submission Type has been saved.")
        form.instance.event = self.request.event
        result = super().form_valid(form)
        if form.has_changed():
            action = "pretalx.submission_type." + (
                "update" if self.object else "create"
            )
            form.instance.log_action(action, person=self.request.user, orga=True)
        return result


class SubmissionTypeDefault(PermissionRequired, View):
    permission_required = "orga.edit_submission_type"

    def get_object(self):
        return get_object_or_404(
            self.request.event.submission_types, pk=self.kwargs.get("pk")
        )

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission_type = self.get_object()
        self.request.event.cfp.default_type = submission_type
        self.request.event.cfp.save(update_fields=["default_type"])
        submission_type.log_action(
            "pretalx.submission_type.make_default", person=self.request.user, orga=True
        )
        messages.success(request, _("The Session Type has been made default."))
        return redirect(self.request.event.cfp.urls.types)


class SubmissionTypeDelete(PermissionRequired, DetailView):
    permission_required = "orga.remove_submission_type"
    template_name = "orga/cfp/submission_type_delete.html"

    def get_object(self):
        return get_object_or_404(
            self.request.event.submission_types, pk=self.kwargs.get("pk")
        )

    def post(self, request, *args, **kwargs):
        submission_type = self.get_object()

        if request.event.submission_types.count() == 1:
            messages.error(
                request,
                _(
                    "You cannot delete the only session type. Try creating another one first!"
                ),
            )
        elif request.event.cfp.default_type == submission_type:
            messages.error(
                request,
                _(
                    "You cannot delete the default session type. Make another type default first!"
                ),
            )
        else:
            try:
                submission_type.delete()
                request.event.log_action(
                    "pretalx.submission_type.delete",
                    person=self.request.user,
                    orga=True,
                )
                messages.success(request, _("The Session Type has been deleted."))
            except ProtectedError:
                messages.error(
                    request,
                    _(
                        "This Session Type is in use in a proposal and cannot be deleted."
                    ),
                )
        return redirect(self.request.event.cfp.urls.types)


class TrackList(EventPermissionRequired, PaginationMixin, ListView):
    template_name = "orga/cfp/track_view.html"
    context_object_name = "tracks"
    permission_required = "orga.view_tracks"

    def get_queryset(self):
        return self.request.event.tracks.all()


class TrackDetail(PermissionRequired, ActionFromUrl, CreateOrUpdateView):
    model = Track
    form_class = TrackForm
    template_name = "orga/cfp/track_form.html"
    permission_required = "orga.view_track"
    write_permission_required = "orga.edit_track"

    def get_success_url(self) -> str:
        return self.request.event.cfp.urls.tracks

    def get_object(self):
        return self.request.event.tracks.filter(pk=self.kwargs.get("pk")).first()

    def get_permission_object(self):
        return self.get_object() or self.request.event

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["event"] = self.request.event
        return result

    def form_valid(self, form):
        form.instance.event = self.request.event
        result = super().form_valid(form)
        messages.success(self.request, _("The track has been saved."))
        if form.has_changed():
            action = "pretalx.track." + ("update" if self.object else "create")
            form.instance.log_action(action, person=self.request.user, orga=True)
        return result


class TrackDelete(PermissionRequired, DetailView):
    permission_required = "orga.remove_track"
    template_name = "orga/cfp/track_delete.html"

    def get_object(self):
        return get_object_or_404(self.request.event.tracks, pk=self.kwargs.get("pk"))

    def post(self, request, *args, **kwargs):
        track = self.get_object()

        try:
            track.delete()
            request.event.log_action(
                "pretalx.track.delete", person=self.request.user, orga=True
            )
            messages.success(request, _("The track has been deleted."))
        except ProtectedError:
            messages.error(
                request,
                _("This track is in use in a proposal and cannot be deleted."),
            )
        return redirect(self.request.event.cfp.urls.tracks)


class AccessCodeList(EventPermissionRequired, PaginationMixin, ListView):
    template_name = "orga/cfp/access_code_view.html"
    context_object_name = "access_codes"
    permission_required = "orga.view_access_codes"

    def get_queryset(self):
        return self.request.event.submitter_access_codes.all().order_by("valid_until")


class AccessCodeDetail(PermissionRequired, CreateOrUpdateView):
    model = SubmitterAccessCode
    form_class = SubmitterAccessCodeForm
    template_name = "orga/cfp/access_code_form.html"
    permission_required = "orga.view_access_code"
    write_permission_required = "orga.edit_access_code"

    def get_success_url(self) -> str:
        return self.request.event.cfp.urls.access_codes

    def get_object(self):
        return self.request.event.submitter_access_codes.filter(
            code__iexact=self.kwargs.get("code")
        ).first()

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["event"] = self.request.event
        if result.get("instance"):
            return result
        if track := self.request.GET.get("track"):
            track = self.request.event.tracks.filter(pk=track).first()
            if track:
                result["initial"]["track"] = track
        return result

    def get_permission_object(self):
        return self.get_object() or self.request.event

    def form_valid(self, form):
        form.instance.event = self.request.event
        result = super().form_valid(form)
        if form.has_changed():
            action = "pretalx.access_code." + ("update" if self.object else "create")
            form.instance.log_action(action, person=self.request.user, orga=True)
        messages.success(self.request, _("The access code has been saved."))
        return result


class AccessCodeSend(PermissionRequired, UpdateView):
    model = SubmitterAccessCode
    form_class = AccessCodeSendForm
    context_object_name = "access_code"
    template_name = "orga/cfp/access_code_send.html"
    permission_required = "orga.view_access_code"

    def get_success_url(self) -> str:
        return self.request.event.cfp.urls.access_codes

    def get_object(self):
        return self.request.event.submitter_access_codes.filter(
            code__iexact=self.kwargs.get("code")
        ).first()

    def get_permission_object(self):
        return self.get_object()

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["user"] = self.request.user
        return result

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, _("The access code has been sent."))
        code = self.get_object()
        code.log_action(
            "pretalx.access_code.send",
            person=self.request.user,
            orga=True,
            data={"email": form.cleaned_data["to"]},
        )
        return result


class AccessCodeDelete(PermissionRequired, DetailView):
    permission_required = "orga.remove_access_code"
    template_name = "orga/cfp/access_code_delete.html"

    def get_object(self):
        return get_object_or_404(
            self.request.event.submitter_access_codes,
            code__iexact=self.kwargs.get("code"),
        )

    def post(self, request, *args, **kwargs):
        access_code = self.get_object()

        try:
            access_code.delete()
            request.event.log_action(
                "pretalx.access_code.delete", person=self.request.user, orga=True
            )
            messages.success(request, _("The access code has been deleted."))
        except ProtectedError:
            messages.error(
                request,
                _(
                    "This access code has been used for a proposal and cannot be deleted. To disable it, you can set its validity date to the past."
                ),
            )
        return redirect(self.request.event.cfp.urls.access_codes)


@method_decorator(csp_update(SCRIPT_SRC="'self' 'unsafe-eval'"), name="dispatch")
class CfPFlowEditor(EventPermissionRequired, TemplateView):
    template_name = "orga/cfp/flow.html"
    permission_required = "orga.edit_cfp"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_configuration"] = (
            self.request.event.cfp_flow.get_editor_config(json_compat=True)
        )
        context["event_configuration"] = {
            "header_pattern": self.request.event.display_settings["header_pattern"]
            or "bg-primary",
            "header_image": (
                self.request.event.header_image.url
                if self.request.event.header_image
                else None
            ),
            "logo_image": (
                self.request.event.logo.url if self.request.event.logo else None
            ),
            "primary_color": self.request.event.get_primary_color(),
            "locales": self.request.event.locales,
        }
        return context

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode())
        except Exception:
            return JsonResponse({"error": "Invalid data"}, status=400)

        flow = CfPFlow(self.request.event)
        if "action" in data and data["action"] == "reset":
            flow.reset()
        else:
            flow.save_config(data)
        return JsonResponse({"success": True})


class TrackOrderView(OrderModelView):
    permission_required = "orga.edit_track"
    model = Track

    def get_success_url(self):
        return self.request.event.cfp.urls.tracks
