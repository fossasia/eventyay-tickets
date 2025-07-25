from django.utils.functional import cached_property
from drf_spectacular.utils import extend_schema_field
from i18nfield.fields import I18nCharField, I18nTextField
from i18nfield.rest_framework import I18nField
from rest_flex_fields import is_expanded
from rest_flex_fields.utils import split_levels
from rest_framework import exceptions
from rest_framework.serializers import ModelSerializer

from pretalx.api.versions import get_api_version_from_request, get_serializer_by_version


class ApiVersionException(exceptions.APIException):
    status_code = 400
    default_detail = "API version not supported."
    default_code = "invalid_version"


class PretalxViewSetMixin:
    endpoint = None
    logtype_map = {
        "create": ".create",
        "update": ".update",
        "partial_update": ".update",
    }

    @cached_property
    def api_version(self):
        try:
            return get_api_version_from_request(self.request)
        except Exception:
            raise ApiVersionException()

    def get_versioned_serializer(self, name):
        try:
            return get_serializer_by_version(name, self.api_version)
        except KeyError:
            raise ApiVersionException()

    def get_serializer_class(self):
        if hasattr(self, "get_unversioned_serializer_class"):
            base_class = self.get_unversioned_serializer_class()
        elif hasattr(self, "serializer_class"):
            base_class = self.serializer_class
        return self.get_versioned_serializer(base_class.__name__)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        locale = self.request.GET.get("lang")
        if locale and locale in self.event.locales:
            context["override_locale"] = locale
        return context

    def perform_create(self, serializer):
        super().perform_create(serializer)
        serializer.instance.log_action(".create", person=self.request.user, orga=True)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        serializer.instance.log_action(".update", person=self.request.user, orga=True)

    @cached_property
    def event(self):
        # request.event is not present when building API docs
        return getattr(self.request, "event", None)

    def has_perm(self, permission, obj=None):
        model = getattr(self, "model", None) or self.queryset.model
        permission_name = model.get_perm(permission)
        return self.request.user.has_perm(permission_name, obj or self.event)

    def check_expanded_fields(self, *args):
        return [arg for arg in args if is_expanded(self.request, arg)]


@extend_schema_field(
    field={
        "type": "object",
        "additionalProperties": {"type": "string"},
        "example": {"en": "English text", "de": "Deutscher Text"},
    },
    component_name="Multi-language string",
)
class DocumentedI18nField(I18nField):
    def to_representation(self, value):
        context = getattr(self.parent, "context", None) or {}
        if context.get("override_locale"):
            return str(value)
        return super().to_representation(value)


class PretalxSerializer(ModelSerializer):
    """
    This serializer class will behave like the i18nfield serializer,
    outputting a dict/object for internationalized strings, unless if
    when it was initialized with an ``override_locale`` (taken from
    a URL queryparam, usually), in which case the string will be cast
    to the locale in question – relying on either a view or a middleware
    to apply the locale manager.
    """

    def __init__(self, *args, **kwargs):
        self.override_locale = kwargs.get("context", {}).get("override_locale")
        self.event = getattr(kwargs.get("context", {}).get("request"), "event", None)
        super().__init__(*args, **kwargs)

    def get_with_fallback(self, data, key):
        """
        Get key from dictionary, or fall back to `self.instance` if it exists.
        Handy for validating data in partial updates.
        (Yes, not terribly safe, but better than nothing.)
        """
        if key in data:
            return data[key]
        if self.instance:
            return getattr(self.instance, key, None)

    @cached_property
    def extra_flex_field_config(self):
        return {
            key: split_levels(self._flex_options_all[key])
            for key in ("expand", "fields", "omit")
        }

    def get_extra_flex_field(self, extra_field, *args, **kwargs):
        if extra_field in self.extra_flex_field_config["expand"][0]:
            klass, settings = self.Meta.extra_expandable_fields[extra_field]
            serializer_class = self._get_serializer_class_from_lazy_string(klass)
            settings["context"] = self.context
            settings["parent"] = self
            for key, value in self.extra_flex_field_config.items():
                if value[1] and extra_field in value[1]:
                    settings[key] = value[1][extra_field]
            return serializer_class(*args, **settings, **kwargs)


PretalxSerializer.serializer_field_mapping[I18nCharField] = DocumentedI18nField
PretalxSerializer.serializer_field_mapping[I18nTextField] = DocumentedI18nField
