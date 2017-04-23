import json


class LogMixin:

    def log_action(self, action, data=None, person=None, orga=False):
        from common.models import ActivityLog
        if data:
            data = json.dumps(data)

        ActivityLog.objects.create(
            event=self.event, person=person, content_object=self,
            action_type=action, data=data
        )

    def logged_actions(self):
        from common.models import ActivityLog

        return ActivityLog.objects.filter(
            content_type=ContentType.objects.get_for_model(type(self)),
            object_id=self.pk
        ).select_related('event', 'person')
