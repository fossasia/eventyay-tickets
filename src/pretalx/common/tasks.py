from django_scopes import scopes_disabled

from pretalx.celery_app import app
from pretalx.common.image import process_image
from pretalx.event.models import Event
from pretalx.person.models import User
from pretalx.submission.models import Submission


@app.task(name="pretalx.process_image")
def task_process_image(*, model: str, pk: int, field: str, generate_thumbnail: bool):
    models = {
        "Event": Event,
        "Submission": Submission,
        "User": User,
    }
    if model not in models:
        return

    with scopes_disabled():
        instance = models[model].objects.filter(pk=pk).first()
        if not instance:
            return

        image = getattr(instance, field, None)
        if not image:
            return

        process_image(image=image, generate_thumbnail=generate_thumbnail)
