from pathlib import Path

from csp.decorators import csp_update
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.forms.models import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    DeleteView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)
from django_context_decorator import context
from django_scopes import scope, scopes_disabled
from formtools.wizard.views import SessionWizardView
from rest_framework.authtoken.models import Token

from pretalx.common.forms import I18nEventFormSet, I18nFormSet
from pretalx.common.mixins.views import (
    ActionFromUrl,
    EventPermissionRequired,
    PermissionRequired,
    SensibleBackWizardMixin,
)
from pretalx.common.models import ActivityLog
from pretalx.common.tasks import regenerate_css
from pretalx.common.templatetags.rich_text import rich_text
from pretalx.common.views import OrderModelView, is_form_bound
from pretalx.event.forms import (
    EventWizardBasicsForm,
    EventWizardCopyForm,
    EventWizardDisplayForm,
    EventWizardInitialForm,
    EventWizardTimelineForm,
)
from pretalx.event.models import Event, Team, TeamInvite
from pretalx.orga.forms import EventForm
from pretalx.orga.forms.event import (
    MailSettingsForm,
    ReviewPhaseForm,
    ReviewScoreCategoryForm,
    ReviewSettingsForm,
    WidgetGenerationForm,
    WidgetSettingsForm,
)
from pretalx.orga.signals import activate_event
from pretalx.person.forms import LoginInfoForm, OrgaProfileForm, UserForm
from pretalx.person.models import User
from pretalx.submission.models import ReviewPhase, ReviewScoreCategory
from pretalx.submission.tasks import recalculate_all_review_scores


class EventSettingsPermission(EventPermissionRequired):
    permission_required = "orga.change_settings"
    write_permission_required = "orga.change_settings"

    @property
    def permission_object(self):
        return self.request.event


class EventDetail(EventSettingsPermission, ActionFromUrl, UpdateView):
    model = Event
    form_class = EventForm
    permission_required = "orga.change_settings"
    template_name = "orga/settings/form.html"

    def get_object(self):
        return self.object

    @cached_property
    def object(self):
        return self.request.event

    def get_form_kwargs(self, *args, **kwargs):
        response = super().get_form_kwargs(*args, **kwargs)
        response["is_administrator"] = self.request.user.is_administrator
        return response

    @context
    def url_placeholder(self):
        return f"https://{self.request.host}/"

    def get_success_url(self) -> str:
        return self.object.orga_urls.settings

    @transaction.atomic
    def form_valid(self, form):
        result = super().form_valid(form)

        form.instance.log_action(
            "pretalx.event.update", person=self.request.user, orga=True
        )
        messages.success(self.request, _("The event settings have been saved."))
        regenerate_css.apply_async(args=(form.instance.pk,))
        return result


class EventLive(EventSettingsPermission, TemplateView):
    template_name = "orga/event/live.html"
    permission_required = "orga.change_settings"

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        warnings = []
        suggestions = []
        # TODO: move to signal
        if (
            not self.request.event.cfp.text
            or len(str(self.request.event.cfp.text)) < 50
        ):
            warnings.append(
                {
                    "text": _("The CfP doesn't have a full text yet."),
                    "url": self.request.event.cfp.urls.text,
                }
            )
        if (
            not self.request.event.landing_page_text
            or len(str(self.request.event.landing_page_text)) < 50
        ):
            warnings.append(
                {
                    "text": _("The event doesn't have a landing page text yet."),
                    "url": self.request.event.orga_urls.settings,
                }
            )
        # TODO: test that mails can be sent
        if (
            self.request.event.feature_flags["use_tracks"]
            and self.request.event.cfp.request_track
            and self.request.event.tracks.count() < 2
        ):
            suggestions.append(
                {
                    "text": _(
                        "You want submitters to choose the tracks for their proposals, but you do not offer tracks for selection. Add at least one track!"
                    ),
                    "url": self.request.event.cfp.urls.tracks,
                }
            )
        if not self.request.event.submission_types.count() > 1:
            suggestions.append(
                {
                    "text": _("You have configured only one session type so far."),
                    "url": self.request.event.cfp.urls.types,
                }
            )
        if not self.request.event.questions.exists():
            suggestions.append(
                {
                    "text": _("You have configured no questions yet."),
                    "url": self.request.event.cfp.urls.new_question,
                }
            )
        result["warnings"] = warnings
        result["suggestions"] = suggestions
        return result

    def post(self, request, *args, **kwargs):
        event = request.event
        action = request.POST.get("action")
        if action == "activate":
            if event.is_public:
                messages.success(request, _("This event was already live."))
            else:
                responses = activate_event.send_robust(event, request=request)
                exceptions = [
                    response[1]
                    for response in responses
                    if isinstance(response[1], Exception)
                ]
                if exceptions:
                    messages.error(
                        request,
                        mark_safe("\n".join(rich_text(e) for e in exceptions)),
                    )
                else:
                    event.is_public = True
                    event.save()
                    event.log_action(
                        "pretalx.event.activate",
                        person=self.request.user,
                        orga=True,
                        data={},
                    )
                    messages.success(request, _("This event is now public."))
                    for response in responses:
                        if isinstance(response[1], str):
                            messages.success(request, response[1])
        else:  # action == 'deactivate'
            if not event.is_public:
                messages.success(request, _("This event was already hidden."))
            else:
                event.is_public = False
                event.save()
                event.log_action(
                    "pretalx.event.deactivate",
                    person=self.request.user,
                    orga=True,
                    data={},
                )
                messages.success(request, _("This event is now hidden."))
        return redirect(event.orga_urls.base)


class EventHistory(EventSettingsPermission, ListView):
    template_name = "orga/event/history.html"
    model = ActivityLog
    context_object_name = "log_entries"
    paginate_by = 200

    def get_queryset(self):
        return ActivityLog.objects.filter(event=self.request.event)


class EventReviewSettings(EventSettingsPermission, ActionFromUrl, FormView):
    form_class = ReviewSettingsForm
    template_name = "orga/settings/review.html"
    write_permission_required = "orga.change_settings"

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.review_settings

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["obj"] = self.request.event
        kwargs["attribute_name"] = "settings"
        kwargs["locales"] = self.request.event.locales
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        try:
            phases = self.save_phases()
            scores = self.save_scores()
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.get(self.request, *self.args, **self.kwargs)
        if not phases or not scores:
            return self.get(self.request, *self.args, **self.kwargs)
        form.save()
        if self.scores_formset.has_changed():
            recalculate_all_review_scores.apply_async(
                kwargs={"event_id": self.request.event.pk}
            )
        return super().form_valid(form)

    @context
    @cached_property
    def phases_formset(self):
        formset_class = inlineformset_factory(
            Event,
            ReviewPhase,
            form=ReviewPhaseForm,
            formset=I18nFormSet,
            can_delete=True,
            extra=0,
        )
        return formset_class(
            self.request.POST if self.request.method == "POST" else None,
            queryset=ReviewPhase.objects.filter(
                event=self.request.event
            ).select_related("event"),
            event=self.request.event,
            prefix="phase",
        )

    def save_phases(self):
        if not self.phases_formset.is_valid():
            return False
        for form in self.phases_formset.initial_forms:
            # Deleting is handled elsewhere, so we skip it here
            if form.has_changed():
                form.instance.event = self.request.event
                form.save()

        extra_forms = [
            form
            for form in self.phases_formset.extra_forms
            if form.has_changed and not self.phases_formset._should_delete_form(form)
        ]
        for form in extra_forms:
            form.instance.event = self.request.event
            form.save()
        return True

    @context
    @cached_property
    def scores_formset(self):
        formset_class = inlineformset_factory(
            Event,
            ReviewScoreCategory,
            form=ReviewScoreCategoryForm,
            formset=I18nEventFormSet,
            can_delete=True,
            extra=0,
        )
        return formset_class(
            self.request.POST if self.request.method == "POST" else None,
            queryset=ReviewScoreCategory.objects.filter(event=self.request.event)
            .select_related("event")
            .prefetch_related("scores"),
            event=self.request.event,
            prefix="scores",
        )

    def save_scores(self):
        if not self.scores_formset.is_valid():
            return False
        weights_changed = False
        for form in self.scores_formset.initial_forms:
            # Deleting is handled elsewhere, so we skip it here
            if form.has_changed():
                if "weight" in form.changed_data:
                    weights_changed = True
                form.instance.event = self.request.event
                form.save()

        extra_forms = [
            form
            for form in self.scores_formset.extra_forms
            if form.has_changed and not self.scores_formset._should_delete_form(form)
        ]
        for form in extra_forms:
            form.instance.event = self.request.event
            form.save()

        if weights_changed:
            ReviewScoreCategory.recalculate_scores(self.request.event)
        return True


class ScoreCategoryDelete(PermissionRequired, View):
    permission_required = "orga.change_settings"

    def get_object(self):
        return get_object_or_404(
            ReviewScoreCategory, event=self.request.event, pk=self.kwargs.get("pk")
        )

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        category = self.get_object()
        category.delete()
        return redirect(self.request.event.orga_urls.review_settings)


class ReviewPhaseOrderView(OrderModelView):
    permission_required = "orga.change_settings"
    model = ReviewPhase

    def get_success_url(self):
        return self.request.event.orga_urls.review_settings


class PhaseDelete(PermissionRequired, View):
    permission_required = "orga.change_settings"

    def get_object(self):
        return get_object_or_404(
            ReviewPhase, event=self.request.event, pk=self.kwargs.get("pk")
        )

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        phase = self.get_object()
        phase.delete()
        return redirect(self.request.event.orga_urls.review_settings)


class PhaseActivate(PermissionRequired, View):
    permission_required = "orga.change_settings"

    def get_object(self):
        return get_object_or_404(
            ReviewPhase, event=self.request.event, pk=self.kwargs.get("pk")
        )

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        phase = self.get_object()
        phase.activate()
        return redirect(self.request.event.orga_urls.review_settings)


class EventMailSettings(EventSettingsPermission, ActionFromUrl, FormView):
    form_class = MailSettingsForm
    template_name = "orga/settings/mail.html"
    write_permission_required = "orga.change_settings"

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.mail_settings

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["obj"] = self.request.event
        kwargs["locales"] = self.request.event.locales
        return kwargs

    def form_valid(self, form):
        form.save()

        if self.request.POST.get("test", "0").strip() == "1":
            backend = self.request.event.get_mail_backend(force_custom=True)
            try:
                backend.test(self.request.event.mail_settings["mail_from"])
            except Exception as e:
                messages.warning(
                    self.request,
                    _("An error occurred while contacting the SMTP server: %s")
                    % str(e),
                )
                return redirect(self.request.event.orga_urls.mail_settings)
            else:  # pragma: no cover
                if form.cleaned_data.get("smtp_use_custom"):
                    messages.success(
                        self.request,
                        _(
                            "Yay, your changes have been saved and the connection attempt to "
                            "your SMTP server was successful."
                        ),
                    )
                else:
                    messages.success(
                        self.request,
                        _(
                            "We've been able to contact the SMTP server you configured. "
                            'Remember to check the "use custom SMTP server" checkbox, '
                            "otherwise your SMTP server will not be used."
                        ),
                    )
        else:
            messages.success(self.request, _("Yay! We saved your changes."))

        return super().form_valid(form)


class InvitationView(FormView):
    template_name = "orga/invitation.html"
    form_class = UserForm

    @context
    @cached_property
    def invitation(self):
        return get_object_or_404(TeamInvite, token__iexact=self.kwargs.get("code"))

    @context
    def password_reset_link(self):
        return reverse("orga:auth.reset")

    def post(self, *args, **kwargs):
        if not self.request.user.is_anonymous:
            self.accept_invite(self.request.user)
            return redirect("/orga/event/")
        return super().post(*args, **kwargs)

    def form_valid(self, form):
        form.save()
        user = User.objects.filter(pk=form.cleaned_data.get("user_id")).first()
        if not user:
            messages.error(
                self.request,
                _(
                    "There was a problem with your authentication. Please contact the organiser for further help."
                ),
            )
            return redirect(self.request.event.urls.base)

        self.accept_invite(user)
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("/orga/event/")

    @transaction.atomic()
    def accept_invite(self, user):
        invite = self.invitation
        invite.team.members.add(user)
        invite.team.save()
        invite.team.organiser.log_action(
            "pretalx.invite.orga.accept", person=user, orga=True
        )
        messages.info(self.request, _("You are now part of the team!"))
        invite.delete()


class UserSettings(TemplateView):
    form_class = LoginInfoForm
    template_name = "orga/user.html"

    def get_success_url(self) -> str:
        return reverse("orga:user.view")

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
        return OrgaProfileForm(
            instance=self.request.user,
            data=self.request.POST if is_form_bound(self.request, "profile") else None,
        )

    @context
    def token(self):
        return Token.objects.filter(
            user=self.request.user
        ).first() or Token.objects.create(user=self.request.user)

    def post(self, request, *args, **kwargs):
        if self.login_form.is_bound and self.login_form.is_valid():
            self.login_form.save()
            messages.success(request, _("Your changes have been saved."))
            request.user.log_action("pretalx.user.password.update")
        elif self.profile_form.is_bound and self.profile_form.is_valid():
            self.profile_form.save()
            messages.success(request, _("Your changes have been saved."))
            request.user.log_action("pretalx.user.profile.update")
        elif request.POST.get("form") == "token":
            request.user.regenerate_token()
            messages.success(
                request,
                _(
                    "Your API token has been regenerated. The previous token will not be usable any longer."
                ),
            )
        else:
            messages.error(
                self.request,
                _("Oh :( We had trouble saving your input. See below for details."),
            )
            return self.get(request, *args, **kwargs)
        return redirect(self.get_success_url())


def condition_copy(wizard):
    return EventWizardCopyForm.copy_from_queryset(wizard.request.user).exists()


class EventWizard(PermissionRequired, SensibleBackWizardMixin, SessionWizardView):
    permission_required = "orga.create_events"
    file_storage = FileSystemStorage(location=Path(settings.MEDIA_ROOT) / "new_event")
    form_list = [
        ("initial", EventWizardInitialForm),
        ("basics", EventWizardBasicsForm),
        ("timeline", EventWizardTimelineForm),
        ("display", EventWizardDisplayForm),
        ("copy", EventWizardCopyForm),
    ]
    condition_dict = {"copy": condition_copy}

    def get_template_names(self):
        return f"orga/event/wizard/{self.steps.current}.html"

    @context
    def has_organiser(self):
        return (
            self.request.user.teams.filter(can_create_events=True).exists()
            or self.request.user.is_administrator
        )

    @context
    def url_placeholder(self):
        return f"https://{self.request.host}/"

    @context
    def organiser(self):
        return (
            self.get_cleaned_data_for_step("initial").get("organiser")
            if self.steps.current != "initial"
            else None
        )

    def render(self, form=None, **kwargs):
        if self.steps.current != "initial":
            if self.get_cleaned_data_for_step("initial") is None:
                return self.render_goto_step("initial")
        if self.steps.current == "timeline":
            fdata = self.get_cleaned_data_for_step("basics")
            year = now().year % 100
            if (
                fdata
                and not str(year) in fdata["slug"]
                and not str(year + 1) in fdata["slug"]
            ):
                messages.warning(
                    self.request,
                    str(
                        _(
                            "Please consider including your event's year in the slug, e.g. myevent{number}."
                        )
                    ).format(number=year),
                )
        elif self.steps.current == "display":
            fdata = self.get_cleaned_data_for_step("timeline")
            if fdata and fdata.get("date_to") < now().date():
                messages.warning(
                    self.request,
                    _("Did you really mean to make your event take place in the past?"),
                )
        return super().render(form, **kwargs)

    def get_form_kwargs(self, step=None):
        kwargs = {"user": self.request.user}
        if step != "initial":
            fdata = self.get_cleaned_data_for_step("initial")
            kwargs.update(fdata or {})
        return kwargs

    @transaction.atomic()
    def done(self, form_list, *args, **kwargs):
        steps = {}
        for step in ("initial", "basics", "timeline", "display", "copy"):
            try:
                steps[step] = self.get_cleaned_data_for_step(step)
            except KeyError:
                steps[step] = {}

        with scopes_disabled():
            event = Event.objects.create(
                organiser=steps["initial"]["organiser"],
                locale_array=",".join(steps["initial"]["locales"]),
                content_locale_array=",".join(steps["initial"]["locales"]),
                name=steps["basics"]["name"],
                slug=steps["basics"]["slug"],
                timezone=steps["basics"]["timezone"],
                email=steps["basics"]["email"],
                locale=steps["basics"]["locale"],
                primary_color=steps["display"]["primary_color"],
                logo=steps["display"]["logo"],
                date_from=steps["timeline"]["date_from"],
                date_to=steps["timeline"]["date_to"],
            )
        with scope(event=event):
            deadline = steps["timeline"].get("deadline")
            if deadline:
                event.cfp.deadline = deadline.replace(tzinfo=event.tz)
                event.cfp.save()
            for setting in ("display_header_data",):
                value = steps["display"].get(setting)
                if value:
                    event.settings.set(setting, value)

        has_control_rights = self.request.user.teams.filter(
            organiser=event.organiser,
            all_events=True,
            can_change_event_settings=True,
            can_change_submissions=True,
        ).exists()
        if not has_control_rights:
            t = Team.objects.create(
                organiser=event.organiser,
                name=_(f"Team {event.name}"),
                can_change_event_settings=True,
                can_change_submissions=True,
            )
            t.members.add(self.request.user)
            t.limit_events.add(event)

        logdata = {}
        for f in form_list:
            logdata.update({k: v for k, v in f.cleaned_data.items()})
        with scope(event=event):
            event.log_action(
                "pretalx.event.create",
                person=self.request.user,
                data=logdata,
                orga=True,
            )

            if steps["copy"] and steps["copy"]["copy_from_event"]:
                event.copy_data_from(
                    steps["copy"]["copy_from_event"],
                    skip_attributes=[
                        "locale",
                        "locales",
                        "primary_color",
                        "timezone",
                        "email",
                        "deadline",
                    ],
                )

        return redirect(event.orga_urls.base + "?congratulations")


class EventDelete(PermissionRequired, DeleteView):
    template_name = "orga/event/delete.html"
    permission_required = "person.is_administrator"
    model = Event

    def get_object(self):
        return self.request.event

    def form_valid(self, request, *args, **kwargs):
        self.get_object().shred()
        return redirect("/orga/")


@method_decorator(csp_update(SCRIPT_SRC="'self' 'unsafe-eval'"), name="dispatch")
class WidgetSettings(EventPermissionRequired, FormView):
    form_class = WidgetSettingsForm
    permission_required = "orga.change_settings"
    template_name = "orga/settings/widget.html"

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _("The widget settings have been saved."))
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["obj"] = self.request.event
        return kwargs

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result["extra_form"] = WidgetGenerationForm(instance=self.request.event)
        return result

    def get_success_url(self) -> str:
        return self.request.event.orga_urls.widget_settings
