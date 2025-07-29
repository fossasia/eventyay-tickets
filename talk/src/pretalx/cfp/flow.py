import copy
import json
import logging
from collections import OrderedDict
from contextlib import suppress
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q
from django.forms import ValidationError
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import Promise, cached_property
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.generic.base import TemplateResponseMixin
from i18nfield.strings import LazyI18nString
from i18nfield.utils import I18nJSONEncoder

from pretalx.cfp.signals import cfp_steps
from pretalx.common.exceptions import SendMailException
from pretalx.common.language import language
from pretalx.common.text.phrases import phrases
from pretalx.person.forms import SpeakerProfileForm, UserForm
from pretalx.person.models import User
from pretalx.submission.forms import InfoForm, QuestionsForm
from pretalx.submission.models import (
    QuestionTarget,
    SubmissionStates,
    SubmissionType,
    Track,
)

logger = logging.getLogger(__name__)


def i18n_string(data, locales):
    if isinstance(data, LazyI18nString):
        return data
    data = copy.deepcopy(data)
    with language("en"):
        if isinstance(data, Promise):
            data = str(data)
        if isinstance(data, str):
            data = {"en": str(data)}
        elif not isinstance(data, dict):
            data = {"en": ""}
        english = data.get("en", "")

    for locale in locales:
        if locale != "en" and not data.get(locale):
            with language(locale):
                data[locale] = gettext(english)
    return LazyI18nString(data)


def serialize_value(value):
    if getattr(value, "pk", None):
        return value.pk
    if getattr(value, "__iter__", None):
        return [serialize_value(element) for element in value]
    if getattr(value, "serialize", None):
        return value.serialize()
    return str(value)


def cfp_session(request):
    request.session.modified = True
    if "cfp" not in request.session or not request.session["cfp"]:
        request.session["cfp"] = {}
    session_data = request.session["cfp"]
    key = request.resolver_match.kwargs["tmpid"]
    if key not in session_data:
        session_data[key] = {
            "data": {},
            "initial": {},
            "files": {},
        }
    return session_data[key]


class BaseCfPStep:
    icon = "pencil"

    def __init__(self, event):
        self.event = event
        self.request = None

    @property
    def identifier(self):
        raise NotImplementedError()

    @property
    def label(self):
        raise NotImplementedError()

    @property
    def priority(self):
        return 100

    def is_applicable(self, request):
        return True

    def is_completed(self, request):
        raise NotImplementedError()

    @cached_property
    def cfp_session(self):
        return cfp_session(self.request)

    def get_next_applicable(self, request):
        next_step = getattr(self, "_next", None)
        if next_step:
            if not next_step.is_applicable(request):
                return next_step.get_next_applicable(request)
            return next_step

    def get_prev_applicable(self, request):
        previous_step = getattr(self, "_previous", None)
        if previous_step:
            if not previous_step.is_applicable(request):
                return previous_step.get_prev_applicable(request)
            return previous_step

    def get_prev_url(self, request):
        prev = self.get_prev_applicable(request)
        if prev:
            return prev.get_step_url(request, query={"draft": False})

    def get_next_url(self, request):
        next_step = self.get_next_applicable(request)
        if next_step:
            return next_step.get_step_url(request)

    def get_step_url(self, request, query=None):
        kwargs = request.resolver_match.kwargs
        kwargs["step"] = self.identifier
        url = reverse("cfp:event.submit", kwargs=kwargs)
        new_query = request.GET.copy()
        query = query or {}
        for key, value in query.items():
            if value is False:
                new_query.pop(key, None)
            else:
                new_query.update({key: value})
        if new_query:
            for key, value in new_query.items():
                if value is False:
                    new_query.pop(key)
            url += f"?{new_query.urlencode()}"
        return url

    def get(self, request):
        return HttpResponseNotAllowed([])

    def post(self, request):
        return HttpResponseNotAllowed([])

    def done(self, request, draft=False):
        pass

    def get_csp_update(self, request):
        pass


class TemplateFlowStep(TemplateResponseMixin, BaseCfPStep):
    template_name = "cfp/event/submission_base.html"

    def get_context_data(self, **kwargs):
        kwargs.setdefault("step", self)
        kwargs.setdefault("event", self.event)
        kwargs.setdefault("prev_url", self.get_prev_url(self.request))
        kwargs.setdefault("next_url", self.get_next_url(self.request))
        kwargs.setdefault(
            "cfp_flow",
            [
                step
                for step in self.event.cfp_flow.steps
                if step.is_applicable(self.request)
            ],
        )
        return kwargs

    def render(self, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get(self, request):
        self.request = request
        return self.render()

    @property
    def identifier(self):
        raise NotImplementedError()


class FormFlowStep(TemplateFlowStep):
    form_class = None
    file_storage = FileSystemStorage(str(Path(settings.MEDIA_ROOT) / "cfp_uploads"))

    def get_form_initial(self):
        initial_data = self.cfp_session.get("initial", {}).get(self.identifier, {})
        previous_data = self.cfp_session.get("data", {}).get(self.identifier, {})
        return copy.deepcopy({**initial_data, **previous_data})

    def get_form(self, from_storage=False):
        if self.request.method == "GET" or from_storage:
            return self.form_class(
                data=self.get_form_initial() if from_storage else None,
                initial=self.get_form_initial(),
                files=self.get_files(),
                **self.get_form_kwargs(),
            )
        return self.form_class(
            data=self.request.POST, files=self.request.FILES, **self.get_form_kwargs()
        )

    def is_completed(self, request):
        self.request = request
        return self.get_form(from_storage=True).is_valid()

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result["form"] = self.get_form()
        previous_data = self.cfp_session.get("data")
        result["submission_title"] = previous_data.get("info", {}).get("title")
        return result

    def post(self, request):
        self.request = request
        form = self.get_form()
        if not form.is_valid():
            error_message = "\n\n".join(
                (f"{form.fields[key].label}: " if key != "__all__" else "")
                + " ".join(values)
                for key, values in form.errors.items()
            )
            messages.error(self.request, error_message)
            return self.get(request)
        self.set_data(form.cleaned_data)
        self.set_files(form.files)
        next_url = self.get_next_url(request)
        return redirect(next_url) if next_url else None

    def set_data(self, data):
        self.cfp_session["data"][self.identifier] = json.loads(
            json.dumps(
                {
                    key: value
                    for key, value in data.items()
                    if not getattr(value, "file", None)
                },
                default=serialize_value,
            )
        )

    def get_files(self):
        saved_files = self.cfp_session["files"].get(self.identifier, {})
        files = {}
        for field, field_dict in saved_files.items():
            field_dict = field_dict.copy()
            tmp_name = field_dict.pop("tmp_name")
            files[field] = UploadedFile(
                file=self.file_storage.open(tmp_name), **field_dict
            )
        return files or None

    def set_files(self, files):
        for field, field_file in files.items():
            tmp_filename = self.file_storage.save(field_file.name, field_file)
            file_dict = {
                "tmp_name": tmp_filename,
                "name": field_file.name,
                "content_type": field_file.content_type,
                "size": field_file.size,
                "charset": field_file.charset,
            }
            data = self.cfp_session["files"].get(self.identifier, {})
            data[field] = file_dict
            self.cfp_session["files"][self.identifier] = data


class GenericFlowStep:
    @cached_property
    def config(self):
        return self.event.cfp_flow.config.get("steps", {}).get(self.identifier, {})

    @property
    def title(self):
        return i18n_string(self.config.get("title", self._title), self.event.locales)

    @property
    def text(self):
        return i18n_string(self.config.get("text", self._text), self.event.locales)

    def get_extra_form_kwargs(self):
        # Used for form kwargs that do not depend on the request/event, but should
        # always be used, particularly in the CfP editor
        return {}

    def get_form_kwargs(self):
        return {
            "event": self.request.event,
            "field_configuration": self.config.get("fields"),
            **self.get_extra_form_kwargs(),
        }

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        result["text"] = self.text
        result["title"] = self.title
        return result


class InfoStep(GenericFlowStep, FormFlowStep):
    identifier = "info"
    icon = "paper-plane"
    form_class = InfoForm
    priority = 0

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result["access_code"] = getattr(self.request, "access_code", None)
        return result

    def get_form_initial(self):
        result = super().get_form_initial()
        for field, model in (("submission_type", SubmissionType), ("track", Track)):
            request_value = self.request.GET.get(field)
            if request_value:
                with suppress(AttributeError, TypeError):
                    pk = int(request_value.split("-")[0])
                    obj = model.objects.filter(event=self.request.event, pk=pk).first()
                    if obj:
                        result[field] = obj
        return result

    def done(self, request, draft=False):
        self.request = request
        form = self.get_form(from_storage=True)
        form.instance.event = self.event
        form.save()
        submission = form.instance
        submission.speakers.add(request.user)
        if draft:
            submission.state = SubmissionStates.DRAFT
            submission.save()
            messages.success(
                self.request,
                _(
                    "Your draft was saved. You can continue to edit it as long as the CfP is open."
                ),
            )
        else:
            submission.log_action("pretalx.submission.create", person=request.user)
            messages.success(
                self.request,
                _(
                    "Congratulations, you’ve submitted your proposal! You can continue to make changes to it "
                    "up to the submission deadline, and you will be notified of any changes or questions."
                ),
            )

            additional_speaker = (
                form.cleaned_data.get("additional_speaker") or ""
            ).strip()
            if additional_speaker:
                try:
                    submission.send_invite(to=[additional_speaker], _from=request.user)
                except SendMailException as exception:
                    logging.getLogger("").warning(str(exception))
                    messages.warning(self.request, phrases.cfp.submission_email_fail)

        access_code = getattr(request, "access_code", None)
        if access_code:
            submission.access_code = access_code
            submission.save()
            access_code.redeemed += 1
            access_code.save()

        request.submission = submission

    @property
    def label(self):
        return phrases.base.general

    @property
    def _title(self):
        return _("Hey, nice to meet you!")

    @property
    def _text(self):
        return _(
            "We’re glad that you want to contribute to our event with your proposal. Let’s get started, this won’t take long."
        )


class QuestionsStep(GenericFlowStep, FormFlowStep):
    identifier = "questions"
    icon = "question-circle-o"
    form_class = QuestionsForm
    template_name = "cfp/event/submission_questions.html"
    priority = 25

    def is_applicable(self, request):
        self.request = request
        info_data = self.cfp_session.get("data", {}).get("info", {})
        track = info_data.get("track")
        if track:
            questions = self.event.questions.exclude(
                Q(target=QuestionTarget.SUBMISSION)
                & (
                    (~Q(tracks__in=[info_data.get("track")]) & Q(tracks__isnull=False))
                    | (
                        ~Q(submission_types__in=[info_data.get("submission_type")])
                        & Q(submission_types__isnull=False)
                    )
                )
            )
        else:
            questions = self.event.questions.exclude(
                Q(target=QuestionTarget.SUBMISSION)
                & (
                    ~Q(submission_types__in=[info_data.get("submission_type")])
                    & Q(submission_types__isnull=False)
                )
            )
        return questions.exists()

    def get_extra_form_kwargs(self):
        return {"target": ""}

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        info_data = self.cfp_session.get("data", {}).get("info", {})
        result["track"] = info_data.get("track")
        access_code = getattr(self.request, "access_code", None)
        if access_code and access_code.submission_type:
            result["submission_type"] = access_code.submission_type
        else:
            result["submission_type"] = info_data.get("submission_type")
        if not self.request.user.is_anonymous:
            result["speaker"] = self.request.user
        return result

    def done(self, request, draft=False):
        form = self.get_form(from_storage=True)
        form.speaker = request.user
        form.submission = request.submission
        form.is_valid()
        form.save()

    @property
    def label(self):
        return _("Additional information")

    @property
    def _title(self):
        return _("Tell us more!")

    @property
    def _text(self):
        return _(
            "Before we can save your proposal, we have some more questions for you."
        )


class UserStep(GenericFlowStep, FormFlowStep):
    identifier = "user"
    icon = "user-circle-o"
    form_class = UserForm
    template_name = "cfp/event/submission_user.html"
    priority = 49

    def is_applicable(self, request):
        return not request.user.is_authenticated

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Needed for support for external auth providers
        context["success_url"] = context["next_url"]
        return context

    def done(self, request, draft=False):
        if not getattr(request.user, "is_authenticated", False):
            form = self.get_form(from_storage=True)
            form.is_valid()
            uid = form.save()
            request.user = User.objects.filter(pk=uid).first()
        # This should never happen
        if not request.user or not request.user.is_active:  # pragma: no cover
            raise ValidationError(
                _(
                    "There was an error when logging in. Please contact the organiser for further help."
                ),
            )
        login(
            request, request.user, backend="django.contrib.auth.backends.ModelBackend"
        )

    @property
    def label(self):
        return _("Account")

    @property
    def _title(self):
        return _(
            "That’s it about your proposal! We now just need a way to contact you."
        )

    @property
    def _text(self):
        return _(
            "To create your proposal, you need an account on this page. This not only gives us a way to contact you, it also gives you the possibility to edit your proposal or to view its current state."
        )


class ProfileStep(GenericFlowStep, FormFlowStep):
    identifier = "profile"
    icon = "address-card-o"
    form_class = SpeakerProfileForm
    template_name = "cfp/event/submission_profile.html"
    priority = 75

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        user_data = copy.deepcopy(self.cfp_session.get("data", {}).get("user", {}))
        if user_data and user_data.get("user_id"):
            result["user"] = User.objects.filter(pk=user_data["user_id"]).first()
        if not result.get("user") and self.request.user.is_authenticated:
            result["user"] = self.request.user
        user = result.get("user")
        result["name"] = user.name if user else user_data.get("register_name")
        result["read_only"] = False
        result["essential_only"] = True
        return result

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        email = getattr(self.request.user, "email", None)
        if email is None:
            data = self.cfp_session.get("data", {}).get("user", {})
            email = data.get("register_email", "")
        if email:
            result["gravatar_parameter"] = User(email=email).gravatar_parameter
        return result

    def done(self, request, draft=False):
        form = self.get_form(from_storage=True)
        form.is_valid()
        form.user = request.user
        form.save()

    @property
    def label(self):
        return _("Profile")

    @property
    def _title(self):
        return _("Tell us something about yourself!")

    @property
    def _text(self):
        return _(
            "This information will be publicly displayed next to your session - you can always edit for as long as proposals are still open."
        )

    def get_csp_update(self, request):
        return {
            "img-src": "https://www.gravatar.com",
            "connect-src": "https://www.gravatar.com",
        }


DEFAULT_STEPS = (
    InfoStep,
    QuestionsStep,
    UserStep,
    ProfileStep,
)


class CfPFlow:
    """An event's CfPFlow contains the list of CfP steps.

    The ``event`` attribute contains the related event and is the only one required
    for instantiation.
    The ``steps`` attribute contains a (linked) list of BaseCfPStep instances.
    The ``steps_dict`` attribute contains an OrderedDict of the same steps.
    The ``config`` attribute contains the additional user configuration, primarily
    from the CfP editor.

    When instantiated with a request during submission time, it will only show
    the forms relevant to the current request. When instantiated without a
    request, for the CfP editor, it will contain all steps.
    """

    def __init__(self, event):
        self.event = event
        data = event.cfp.settings["flow"]
        self.config = self.get_config(data)

        steps = [step(event=event) for step in DEFAULT_STEPS]
        for __, response in cfp_steps.send_robust(self.event):
            for step_class in response:
                steps.append(step_class(event=event))
        steps = sorted(steps, key=lambda step: step.priority)
        self.steps_dict = OrderedDict()
        for step in steps:
            self.steps_dict[step.identifier] = step
        previous_step = None
        for step in steps:
            step._previous = previous_step
            if previous_step:
                previous_step._next = step
            previous_step = step

    def get_config(self, data, json_compat=False):
        if isinstance(data, str) and data:
            data = json.loads(data)
        if not isinstance(data, dict):
            return {}

        config = {"steps": {}}
        steps = data.get("steps", {})
        if isinstance(steps, list):  # This is what we get from the editor
            for entry in steps:
                config["steps"][entry["identifier"]] = self._get_step_config_from_data(
                    entry
                )
        else:
            for key, value in steps.items():
                config["steps"][key] = self._get_step_config_from_data(value)
        if json_compat:
            config = json.loads(json.dumps(config, cls=I18nJSONEncoder))
        return config

    def get_editor_config(self, json_compat=False):
        config = self.config
        locales = self.event.locales
        steps = []
        for step in self.steps:
            step_config = config.get("steps", {}).get(step.identifier, {})
            if not isinstance(step, GenericFlowStep) or step.identifier == "user":
                continue
            steps.append(
                {
                    "icon": step.icon,
                    "icon_label": step.label,
                    "title": i18n_string(step_config.get("title", step.title), locales),
                    "text": i18n_string(step_config.get("text", step.text), locales),
                    "identifier": step.identifier,
                    "fields": [
                        {
                            "widget": field.widget.__class__.__name__,
                            "key": key,
                            "label": i18n_string(field.label, locales),
                            "help_text": i18n_string(
                                getattr(field, "original_help_text", field.help_text),
                                locales,
                            ),
                            "added_help_text": i18n_string(
                                getattr(field, "added_help_text", ""),
                                locales,
                            ),
                            "full_help_text": field.help_text,
                            "required": field.required,
                        }
                        for key, field in step.form_class(
                            event=self.event,
                            field_configuration=step_config.get("fields"),
                            **step.get_extra_form_kwargs(),
                        ).fields.items()
                    ],
                }
            )
        if json_compat:
            steps = json.loads(json.dumps(steps, cls=I18nJSONEncoder))
        return steps

    def get_config_json(self):
        return json.dumps(self.config, cls=I18nJSONEncoder)

    def save_config(self, data):
        if isinstance(data, list) or (isinstance(data, dict) and "steps" not in data):
            data = {"steps": data}
        data = self.get_config(data, json_compat=True)
        self.event.cfp.settings["flow"] = data
        self.event.cfp.save()

    def reset(self):
        self.save_config(None)

    def _get_step_config_from_data(self, data):
        step_config = {}
        locales = self.event.locales
        for i18n_configurable in ("title", "text", "label"):
            if i18n_configurable in data:
                step_config[i18n_configurable] = i18n_string(
                    data[i18n_configurable], locales
                )
        for configurable in ("icon",):
            if configurable in data:
                step_config[configurable] = data[configurable]

        step_config["fields"] = []
        for config_field in data.get("fields", []):
            field = {}
            for key in ("help_text", "request", "required", "key", "label"):
                if key in config_field:
                    field[key] = (
                        i18n_string(config_field[key], locales)
                        if key in ("help_text", "label")
                        else config_field[key]
                    )
            step_config["fields"].append(field)
        return step_config

    @property
    def steps(self):
        return list(self.steps_dict.values())
