from venueless.celery import app
from venueless.core.models import World


class WorldTask(app.Task):
    def __call__(self, *args, **kwargs):
        if "world_id" in kwargs:
            world_id = kwargs.get("world_id")
            world = World.objects.get(pk=world_id)
            del kwargs["world_id"]
            kwargs["world"] = world
        elif "world" in kwargs:
            world_id = kwargs.get("world")
            world = World.objects.get(pk=world_id)
            kwargs["world"] = world
        else:
            args = list(args)
            world_id = args[0]
            world = World.objects.get(pk=world_id)
            args[0] = world

        return super().__call__(*args, **kwargs)
