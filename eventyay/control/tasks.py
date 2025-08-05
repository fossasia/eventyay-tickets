from eventyay.celery_app import app
from eventyay.core.tasks import EventTask


@app.task(base=EventTask)
def clear_event_data(event):
    event.clear_data()
