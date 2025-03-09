from django.conf import settings
from django.core.validators import URLValidator
from i18nfield.fields import I18nCharField, I18nTextField
from i18nfield.strings import LazyI18nString
from rest_framework.exceptions import ValidationError
from rest_framework.fields import Field
from rest_framework.serializers import ModelSerializer


class I18nField(Field):
    def __init__(self, **kwargs):
        self.allow_blank = kwargs.pop("allow_blank", False)
        self.trim_whitespace = kwargs.pop("trim_whitespace", True)
        self.max_length = kwargs.pop("max_length", None)
        self.min_length = kwargs.pop("min_length", None)
        super().__init__(**kwargs)

    def to_representation(self, value):
        if hasattr(value, "data"):
            if isinstance(value.data, dict):
                return value.data
            elif value.data is None:
                return None
            else:
                return {settings.LANGUAGE_CODE: str(value.data)}
        elif value is None:
            return None
        else:
            return {settings.LANGUAGE_CODE: str(value)}

    def to_internal_value(self, data):
        if isinstance(data, str):
            return LazyI18nString(data)
        elif isinstance(data, dict):
            if any([k not in dict(settings.LANGUAGES) for k in data.keys()]):
                raise ValidationError("Invalid languages included.")
            return LazyI18nString(data)
        else:
            raise ValidationError("Invalid data type.")


class I18nAwareModelSerializer(ModelSerializer):
    pass


I18nAwareModelSerializer.serializer_field_mapping[I18nCharField] = I18nField
I18nAwareModelSerializer.serializer_field_mapping[I18nTextField] = I18nField


class I18nURLField(I18nField):
    """
    Custom field to handle internationalized URL inputs. It extends the I18nField
    and ensures that all provided URLs are valid.

    Methods:
        to_internal_value(value: LazyI18nString) -> LazyI18nString:
            Validates the URL(s) in the provided internationalized input.
    """

    def to_internal_value(self, value) -> LazyI18nString:
        """
        Converts and validates the internationalized URL input.

        Args:
            value (LazyI18nString): The input value to convert and validate.

        Returns:
            LazyI18nString: The converted and validated input value.

        Raises:
            ValidationError: If any of the URLs are invalid.
        """
        value = super().to_internal_value(value)
        if not value:
            return value

        url_validator = URLValidator()

        if isinstance(value.data, dict):
            for val in value.data.values():
                if val:
                    url_validator(val)
        else:
            url_validator(value.data)

        return value
