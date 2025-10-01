import json
from contextlib import suppress

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, models
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django_scopes import ScopedManager, scopes_disabled
from i18nfield.utils import I18nJSONEncoder
from rules.contrib.models import RulesModelBase, RulesModelMixin

from eventyay.helpers.json import CustomJSONEncoder

SENSITIVE_KEYS = ['password', 'secret', 'api_key']


class TimestampedModel(models.Model):
    created = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        abstract = True


class LogMixin:
    log_prefix = None
    log_parent = None

    def log_action(self, action, data=None, user=None, api_token=None, auth=None, person=None, orga=False, content_object=None, save=True):
        """
        Create a LogEntry (instead of ActivityLog), similar to LoggingMixin.
        """
        if not getattr(self, 'pk', None):
            return

        if action.startswith('.'):
            if self.log_prefix:
                action = f'{self.log_prefix}{action}'
            else:
                return

        from .log import LogEntry
        from .event import Event
        from .devices import Device
        from .organizer import TeamAPIToken
        from eventyay.api.models import OAuthAccessToken, OAuthApplication
        from ..services.notifications import notify
        from eventyay.api.webhooks import notify_webhooks

        # Resolve event
        event = None
        if isinstance(self, Event):
            event = self
        elif hasattr(self, 'event'):
            event = self.event

        # Ensure user is authenticated
        if user and not getattr(user, "is_authenticated", True):
            user = None

        # Auth / token mapping
        kwargs = {}
        if isinstance(auth, OAuthAccessToken):
            kwargs['oauth_application'] = auth.application
        elif isinstance(auth, OAuthApplication):
            kwargs['oauth_application'] = auth
        elif isinstance(auth, TeamAPIToken):
            kwargs['api_token'] = auth
        elif isinstance(auth, Device):
            kwargs['device'] = auth
        elif isinstance(api_token, TeamAPIToken):
            kwargs['api_token'] = api_token

        # Sanitize data
        if isinstance(data, dict):
            sensitive_keys = ['password', 'secret', 'api_key']
            for sensitive in sensitive_keys:
                for k, v in data.items():
                    if sensitive in k and v:
                        data[k] = '********'
            data = json.dumps(data, cls=CustomJSONEncoder, sort_keys=True)
        elif data:
            raise TypeError(f'Logged data should always be a dictionary, not {type(data)}.')

        log_entry = LogEntry.objects.create(
            content_object=content_object or self,
            user=user or person,
            action_type=action,
            event=event,
            data=data,
            is_orga_action=orga,
            **kwargs
        )

        if save:
            log_entry.save()
            if getattr(log_entry, 'notification_type', None):
                notify.apply_async(args=(log_entry.pk,))
            if getattr(log_entry, 'webhook_type', None):
                notify_webhooks.apply_async(args=(log_entry.pk,))

        return log_entry

    def logged_actions(self):
        """Return all logs for this object."""
        from .log import LogEntry
        from django.contrib.contenttypes.models import ContentType

        return (
            LogEntry.objects.filter(
                content_type=ContentType.objects.get_for_model(type(self)),
                object_id=self.pk,
            )
            .select_related('event', 'user')
            .prefetch_related('content_object')
        )

    def delete(self, *args, log_kwargs=None, **kwargs):
        parent = self.log_parent
        result = super().delete(*args, **kwargs)
        if parent and getattr(parent, 'log_action', None):
            log_kwargs = log_kwargs or {}
            parent.log_action(f'{self.log_prefix}.delete', **log_kwargs)
        return result


class FileCleanupMixin:
    """Deletes all uploaded files when object is deleted."""

    @cached_property
    def _file_fields(self):
        return [field.name for field in self._meta.fields if isinstance(field, models.FileField)]

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields', None)
        if not self.pk or (update_fields and not set(self._file_fields) & set(update_fields)):
            return super().save(*args, **kwargs)

        try:
            pre_save_instance = self.__class__.objects.get(pk=self.pk)
        except Exception:
            return super().save(*args, **kwargs)

        for field in self._file_fields:
            old_value = getattr(pre_save_instance, field)
            if old_value:
                new_value = getattr(self, field)
                if new_value and old_value.path != new_value.path:
                    # We don't want to delete the file immediately, as the save action
                    # that triggered this task might still fail, so we schedule the
                    # deletion for 10 seconds in the future, and pass the file field
                    # to check if the file is still in use.
                    from eventyay.common.tasks import task_cleanup_file

                    task_cleanup_file.apply_async(
                        kwargs={
                            'model': str(self._meta.model_name.capitalize()),
                            'pk': self.pk,
                            'field': field,
                            'path': old_value.path,
                        },
                        countdown=10,
                    )
        return super().save(*args, **kwargs)

    def _delete_files(self):
        for field in self._file_fields:
            value = getattr(self, field, None)
            if value:
                with suppress(Exception):
                    value.delete(save=False)

    def delete(self, *args, **kwargs):
        self._delete_files()
        return super().delete(*args, **kwargs)

    def process_image(self, field, generate_thumbnail=False):
        from eventyay.common.tasks import task_process_image

        task_process_image.apply_async(
            kwargs={
                'field': field,
                'model': str(self._meta.model_name.capitalize()),
                'pk': self.pk,
                'generate_thumbnail': generate_thumbnail,
            },
            countdown=10,
        )


class PretalxModel(
    LogMixin,
    TimestampedModel,
    FileCleanupMixin,
    RulesModelMixin,
    models.Model,
    metaclass=RulesModelBase,
):
    """
    Base model for most pretalx models. Suitable for plugins.
    """

    objects = ScopedManager(event='event')

    class Meta:
        abstract = True


class GenerateCode:
    """Generates a random code on first save.

    Omits some character pairs because they are hard to
    read/differentiate: 1/I, O/0, 2/Z, 4/A, 5/S, 6/G.
    """

    _code_length = 6
    _code_charset = list('ABCDEFGHJKLMNPQRSTUVWXYZ3789')
    _code_property = 'code'

    @classmethod
    def generate_code(cls, length=None):
        length = length or cls._code_length
        return get_random_string(length=length, allowed_chars=cls._code_charset)

    def assign_code(self, length=None):
        length = length or self._code_length
        while True:
            code = self.generate_code(length=length)
            with scopes_disabled():
                if not self.__class__.objects.filter(**{f'{self._code_property}__iexact': code}).exists():
                    setattr(self, self._code_property, code)
                    return

    def save(self, *args, **kwargs):
        # It’s super duper unlikely for this to fail, but let’s add a short
        # stupid retry loop regardless
        for _ in range(3):
            if not getattr(self, self._code_property, None):
                self.assign_code()
            try:
                return super().save(*args, **kwargs)
            except IntegrityError:
                setattr(self, self._code_property, None)


class OrderedModel:
    """Provides methods to move a model up and down in a queryset.

    Implement the `get_order_queryset` method as a classmethod or staticmethod
    to provide the queryset to order.
    """

    order_field = 'position'
    order_up_url = 'urls.up'
    order_down_url = 'urls.down'

    @staticmethod
    def get_order_queryset(**kwargs):
        raise NotImplementedError

    def _get_attribute(self, attribute):
        result = self
        for part in attribute.split('.'):
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
