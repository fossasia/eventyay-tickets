from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils.formats import date_format
from django.utils.timezone import get_current_timezone
from django.utils.translation import gettext_lazy as _
from zxcvbn import zxcvbn


class ZXCVBNValidator:
    DEFAULT_USER_ATTRIBUTES = ("first_name", "last_name", "email")

    def __init__(self, min_score=3, user_attributes=DEFAULT_USER_ATTRIBUTES):
        if not 0 <= min_score <= 4:
            raise Exception("min_score must be between 0 and 4!")
        self.min_score = min_score
        self.user_attributes = user_attributes

    def __call__(self, value):
        return self.validate(value)

    def validate(self, password, user=None):
        user_inputs = [
            getattr(user, attribute, None) for attribute in self.user_attributes
        ]
        user_inputs = [attr for attr in user_inputs if attr is not None]
        results = zxcvbn(password, user_inputs=user_inputs)
        if results.get("score", 0) < self.min_score:
            feedback = ", ".join(results.get("feedback", {}).get("suggestions", []))
            raise ValidationError(_(feedback), params={})


class MinDateValidator(MinValueValidator):
    def __call__(self, value):
        try:
            return super().__call__(value)
        except forms.ValidationError as e:
            e.params["limit_value"] = date_format(
                e.params["limit_value"], "SHORT_DATE_FORMAT"
            )
            raise e


class MinDateTimeValidator(MinValueValidator):
    def __call__(self, value):
        try:
            return super().__call__(value)
        except forms.ValidationError as e:
            e.params["limit_value"] = date_format(
                e.params["limit_value"].astimezone(get_current_timezone()),
                "SHORT_DATETIME_FORMAT",
            )
            raise e


class MaxDateValidator(MaxValueValidator):
    def __call__(self, value):
        try:
            return super().__call__(value)
        except forms.ValidationError as e:
            e.params["limit_value"] = date_format(
                e.params["limit_value"], "SHORT_DATE_FORMAT"
            )
            raise e


class MaxDateTimeValidator(MaxValueValidator):
    def __call__(self, value):
        try:
            return super().__call__(value)
        except forms.ValidationError as e:
            e.params["limit_value"] = date_format(
                e.params["limit_value"].astimezone(get_current_timezone()),
                "SHORT_DATETIME_FORMAT",
            )
            raise e
