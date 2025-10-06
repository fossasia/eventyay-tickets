from eventyay.celery_app import app
from eventyay.base.models import Event


class EventTask(app.Task):
    def __call__(self, *args, **kwargs):
        if "event_id" in kwargs:
            event_id = kwargs.get("event_id")
            event = Event.objects.get(pk=event_id)
            del kwargs["event_id"]
            kwargs["event"] = event
        elif "event" in kwargs:
            event_id = kwargs.get("event")
            event = Event.objects.get(pk=event_id)
            kwargs["event"] = event
        else:
            args = list(args)
            event_id = args[0]
            event = Event.objects.get(pk=event_id)
            args[0] = event

        return super().__call__(*args, **kwargs)
