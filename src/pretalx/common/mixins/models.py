import json

from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify
from i18nfield.utils import I18nJSONEncoder

SENSITIVE_KEYS = ['password', 'secret', 'api_key']


class LogMixin:
    def log_action(self, action, data=None, person=None, orga=False):
        if not self.pk:
            return

        from pretalx.common.models import ActivityLog

        if data and isinstance(data, dict):
            for key, value in data.items():
                if any(sensitive_key in key for sensitive_key in SENSITIVE_KEYS):
                    value = data[key]
                    data[key] = '********' if value else value
            data = json.dumps(data, cls=I18nJSONEncoder)
        elif data:
            raise TypeError('Logged data should always be a dictionary.')

        ActivityLog.objects.create(
            event=getattr(self, 'event', None),
            person=person,
            content_object=self,
            action_type=action,
            data=data,
            is_orga_action=orga,
        )

    def logged_actions(self):
        from pretalx.common.models import ActivityLog

        return ActivityLog.objects.filter(
            content_type=ContentType.objects.get_for_model(type(self)),
            object_id=self.pk,
        ).select_related('event', 'person')


class IdBasedSlug:
    """
    Adds a method to retrieve a human-understandable slug based on the `id` field of a model.
    """

    slug_separator = '-'

    def slug(self):
        """
        Get slug of this object.
        """
        return f'{self.id}{self.slug_separator}{slugify(self.name)}'

    @classmethod
    def id_from_slug(cls, slug):
        """
        Get ID from slug value.
        """
        return int(slug.split(cls.slug_separator)[0])
