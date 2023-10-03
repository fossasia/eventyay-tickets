import json
from contextlib import suppress

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.crypto import get_random_string
from django_scopes import ScopedManager, scopes_disabled
from i18nfield.utils import I18nJSONEncoder

SENSITIVE_KEYS = ["password", "secret", "api_key"]


class TimestampedModel(models.Model):
    created = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        abstract = True


class LogMixin:
    def log_action(self, action, data=None, person=None, orga=False):
        if not self.pk:
            return

        from pretalx.common.models import ActivityLog

        if data and isinstance(data, dict):
            for key, value in data.items():
                if any(sensitive_key in key for sensitive_key in SENSITIVE_KEYS):
                    value = data[key]
                    data[key] = "********" if value else value
            data = json.dumps(data, cls=I18nJSONEncoder)
        elif data:
            raise TypeError(
                f"Logged data should always be a dictionary, not {type(data)}."
            )

        return ActivityLog.objects.create(
            event=getattr(self, "event", None),
            person=person,
            content_object=self,
            action_type=action,
            data=data,
            is_orga_action=orga,
        )

    def logged_actions(self):
        from pretalx.common.models import ActivityLog

        return (
            ActivityLog.objects.filter(
                content_type=ContentType.objects.get_for_model(type(self)),
                object_id=self.pk,
            )
            .select_related("event", "person")
            .prefetch_related("content_object")
        )


class FileCleanupMixin:
    """Deletes all uploaded files when object is deleted."""

    def _delete_files(self):
        file_attributes = [
            field.name
            for field in self._meta.fields
            if isinstance(field, models.FileField)
        ]
        for field in file_attributes:
            value = getattr(self, field, None)
            if value:
                with suppress(Exception):
                    value.delete(save=False)

    def delete(self, *args, **kwargs):
        self._delete_files()
        return super().delete(*args, **kwargs)


class PretalxModel(LogMixin, TimestampedModel, FileCleanupMixin, models.Model):
    """
    Base model for most pretalx models. Suitable for plugins.
    """

    objects = ScopedManager(event="event")

    class Meta:
        abstract = True


class GenerateCode:
    """Generates a random code on first save.

    Omits some character pairs because they are hard to
    read/differentiate: 1/I, O/0, 2/Z, 4/A, 5/S, 6/G.
    """

    _code_length = 6
    _code_charset = list("ABCDEFGHJKLMNPQRSTUVWXYZ3789")
    _code_property = "code"

    @classmethod
    def generate_code(cls, length=None):
        length = length or cls._code_length
        return get_random_string(length=length, allowed_chars=cls._code_charset)

    def assign_code(self, length=None):
        length = length or self._code_length
        while True:
            code = self.generate_code(length=length)
            with scopes_disabled():
                if not self.__class__.objects.filter(
                    **{f"{self._code_property}__iexact": code}
                ).exists():
                    setattr(self, self._code_property, code)
                    return

    def save(self, *args, **kwargs):
        if not getattr(self, self._code_property, None):
            self.assign_code()
        return super().save(*args, **kwargs)


class OrderedModel:
    """Provides methods to move a model up and down in a queryset.

    Used with OrderModelView to provide a view to move models up and down.
    Implement the `get_order_queryset` method as a classmethod or staticmethod
    to provide the queryset to order.
    """

    order_field = "position"
    order_up_url = "urls.up"
    order_down_url = "urls.down"

    @staticmethod
    def get_order_queryset(**kwargs):
        raise NotImplementedError

    def _get_attribute(self, attribute):
        result = self
        for part in attribute.split("."):
            result = getattr(result, part)
        return result

    def get_down_url(self):
        return self._get_attribute(self.order_down_url)

    def get_up_url(self):
        return self._get_attribute(self.order_up_url)

    def up(self):
        return self._move(up=True)

    def down(self):
        return self._move(up=False)

    @property
    def order_queryset(self):
        return self.get_order_queryset(event=self.event)

    def move(self, up=True):
        queryset = list(self.order_queryset.order_by(self.order_field))
        index = queryset.index(self)
        if index != 0 and up:
            queryset[index - 1], queryset[index] = queryset[index], queryset[index - 1]
        elif index != len(queryset) - 1 and not up:
            queryset[index + 1], queryset[index] = queryset[index], queryset[index + 1]

        for index, element in enumerate(queryset):
            if element.position != index:
                element.position = index
                element.save()

    move.alters_data = True
