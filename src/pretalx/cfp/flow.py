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
from django.utils.functional import cached_property
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.generic.base import TemplateResponseMixin
from i18nfield.strings import LazyI18nString
from i18nfield.utils import I18nJSONEncoder

from pretalx.cfp.signals import cfp_steps
from pretalx.common.mail import SendMailException
from pretalx.common.phrases import phrases
from pretalx.common.utils import language
from pretalx.person.forms import SpeakerProfileForm, UserForm
from pretalx.person.models import User
from pretalx.submission.forms import InfoForm, QuestionsForm
from pretalx.submission.models import QuestionTarget, SubmissionType, Track


def i18n_string(data, locales):
    if isinstance(data, LazyI18nString):
        return data
    data = copy.deepcopy(data)
    with language("en"):
        if getattr(data, "_proxy____prepared", None):
            data = str(data)
        if isinstance(data, str):
            data = {"en": str(data)}
        if not isinstance(data, dict):
            data = {"en": ""}
        english = data.get("en", "")

    for locale in locales:
        if locale != "en" and not data.get(locale):
            with language(locale):
                data[locale] = gettext(english)
    return LazyI18nString(data)


def cfp_session(request):
    request.session.modified = True
    if "cfp" not in request.session or not request.session["cfp"]:
        request.session["cfp"] = {}
    key = request.resolver_match.kwargs["tmpid"]
    if key not in request.session["cfp"]:
        request.session["cfp"][key] = {
            "data": {},
            "initial": {},
            "files": {},
        }
    return request.session["cfp"][key]


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

    def is_completed(self, request, warn=False):
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
            return prev.get_step_url(request)

    def get_next_url(self, request):
        n = self.get_next_applicable(request)
        if n:
            return n.get_step_url(request)

    def get_step_url(self, request):
        kwargs = request.resolver_match.kwargs
        kwargs["step"] = self.identifier
        url = reverse("cfp:event.submit", kwargs=kwargs)
        if request.GET:
            url += f"?{request.GET.urlencode()}"
        return url

    def get(self, request):
        return HttpResponseNotAllowed([])

    def post(self, request):
        return HttpResponseNotAllowed([])

    def done(self, request):
        pass


class TemplateFlowStep(TemplateResponseMixin, BaseCfPStep):
    template_name = "cfp/event/submission_step.html"

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
                data=self.get_form_initial() or None,
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
        return result

    def post(self, request):
        self.request = request
        form = self.get_form()
        if not form.is_valid():
            return self.get(request)
        self.set_data(form.cleaned_data)
        self.set_files(form.files)
        next_url = self.get_next_url(request)
        return redirect(next_url) if next_url else None

    def set_data(self, data):
        def serialize_value(value):
            if getattr(value, "file", None):
                return None
            if getattr(value, "pk", None):
                return value.pk
            if getattr(value, "__iter__", None):
                return [serialize_value(v) for v in value]
            if getattr(value, "serialize", None):
                return value.serialize()
            return str(value)

        self.cfp_session["data"][self.identifier] = json.loads(
            json.dumps(data, default=serialize_value)
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

    def get_form_kwargs(self):
        return {
            "event": self.request.event,
            "field_configuration": self.config.get("fields"),
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

    @property
    def label(self):
        return _("General")

    @property
    def _title(self):
        return _("Hey, nice to meet you!")

    @property
    def _text(self):
        return _(
            "We're glad that you want to contribute to our event with your submission. Let's get started, this won't take long."
        )

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

    def done(self, request):
        self.request = request
        form = self.get_form(from_storage=True)
        form.instance.event = self.event
        form.save()
        submission = form.instance
        submission.speakers.add(request.user)
        submission.log_action("pretalx.submission.create", person=request.user)
        messages.success(request, phrases.cfp.submission_success)

        additional_speaker = form.cleaned_data.get("additional_speaker").strip()
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


class QuestionsStep(GenericFlowStep, FormFlowStep):
    identifier = "questions"
    icon = "question-circle-o"
    form_class = QuestionsForm
    template_name = "cfp/event/submission_questions.html"
    priority = 25

    @property
    def label(self):
        return _("Questions")

    @property
    def _title(self):
        return _("Tell us more!")

    @property
    def _text(self):
        return _(
            "Before we can save your submission, we have some more questions for you."
        )

    def is_applicable(self, request):
        self.request = request
        info_data = self.cfp_session.get("data", {}).get("info", {})
        if not info_data or not info_data.get("track"):
            return self.event.questions.all().exists()
        return self.event.questions.exclude(
            Q(target=QuestionTarget.SUBMISSION)
            & (
                (~Q(tracks__in=[info_data.get("track")]) & Q(tracks__isnull=False))
                | (
                    ~Q(submission_types__in=[info_data.get("submission_type")])
                    & Q(submission_types__isnull=False)
                )
            )
        ).exists()

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        info_data = self.cfp_session.get("data", {}).get("info", {})
        result["target"] = ""
        result["track"] = info_data.get("track")
        result["submission_type"] = info_data.get("submission_type")
        if not self.request.user.is_anonymous:
            result["speaker"] = self.request.user
        return result

    def done(self, request):
        form = self.get_form(from_storage=True)
        form.speaker = request.user
        form.submission = request.submission
        form.is_valid()
        form.save()


class UserStep(GenericFlowStep, FormFlowStep):
    identifier = "user"
    icon = "user-circle-o"
    form_class = UserForm
    template_name = "cfp/event/submission_user.html"
    priority = 49

    @property
    def label(self):
        return _("Account")

    @property
    def _title(self):
        return _(
            "That's it about your submission! We now just need a way to contact you."
        )

    @property
    def _text(self):
        return _(
            "To create your submission, you need an account on this page. This not only gives us a way to contact you, it also gives you the possibility to edit your submission or to view its current state."
        )

    def is_applicable(self, request):
        return not request.user.is_authenticated

    def done(self, request):
        if not getattr(request.user, "is_authenticated", False):
            form = self.get_form(from_storage=True)
            form.is_valid()
            uid = form.save()
            request.user = User.objects.filter(pk=uid).first()
        if not request.user or not request.user.is_active:
            raise ValidationError(
                _(
                    "There was an error when logging in. Please contact the organiser for further help."
                ),
            )
        login(
            request, request.user, backend="django.contrib.auth.backends.ModelBackend"
        )


class ProfileStep(GenericFlowStep, FormFlowStep):
    identifier = "profile"
    icon = "address-card-o"
    form_class = SpeakerProfileForm
    template_name = "cfp/event/submission_profile.html"
    priority = 75

    @property
    def label(self):
        return _("Account")

    @property
    def _title(self):
        return _("Tell us something about yourself!")

    @property
    def _text(self):
        return _(
            "This information will be publicly displayed next to your talk - you can always edit for as long as submissions are still open."
        )

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

    def done(self, request):
        form = self.get_form(from_storage=True)
        form.is_valid()
        form.user = request.user
        form.save()


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

    event = None

    def __init__(self, event):
        self.event = event
        data = event.settings.cfp_flow
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

    @property
    def steps(self):
        return list(self.steps_dict.values())

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
                    "title": step_config.get("title", step.title),
                    "text": step_config.get("text", step.text),
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
                                getattr(field, "added_help_text", ""), locales,
                            ),
                            "full_help_text": field.help_text,
                            "required": field.required,
                        }
                        for key, field in step.form_class(
                            event=self.event,
                            field_configuration=step_config.get("fields"),
                        ).fields.items()
                    ],
                }
            )
        if json_compat:
            steps = json.loads(json.dumps(steps, cls=I18nJSONEncoder))
        return steps

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
            for key in ("help_text", "request", "required", "key"):
                if key in config_field:
                    field[key] = (
                        i18n_string(config_field[key], locales)
                        if key == "help_text"
                        else config_field[key]
                    )
            step_config["fields"].append(field)
        return step_config

    def get_config_json(self):
        return json.dumps(self.config, cls=I18nJSONEncoder)

    def save_config(self, data):
        if isinstance(data, list) or (isinstance(data, dict) and "steps" not in data):
            data = {"steps": data}
        data = self.get_config(data, json_compat=True)
        self.event.settings.cfp_flow = data

    def reset(self):
        self.save_config(None)
