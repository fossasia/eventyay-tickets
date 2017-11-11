import json

from django.contrib.contenttypes.models import ContentType
from i18nfield.utils import I18nJSONEncoder


class LogMixin:

    def log_action(self, action, data=None, person=None, orga=False):
        if not self.pk:
            return

        from pretalx.common.models import ActivityLog
        if data:
            data = json.dumps(data, cls=I18nJSONEncoder)

        ActivityLog.objects.create(
            event=self.event, person=person, content_object=self,
            action_type=action, data=data, is_orga_action=orga,
        )

    def logged_actions(self):
        from pretalx.common.models import ActivityLog

        return ActivityLog.objects.filter(
            content_type=ContentType.objects.get_for_model(type(self)),
            object_id=self.pk
        ).select_related('event', 'person')
