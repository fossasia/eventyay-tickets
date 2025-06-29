from eventyay.celery_app import app
from eventyay.base.core.tasks import WorldTask


@app.task(base=WorldTask)
def clear_world_data(world):
    world.clear_data()
