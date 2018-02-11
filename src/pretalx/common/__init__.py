from contextlib import suppress

from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = 'pretalx.common'

    def ready(self):
        from pretalx.event.models import Event
        from pretalx.common.tasks import regenerate_css
        from django.db import connection, utils
        from . import signals  # noqa

        if Event._meta.db_table not in connection.introspection.table_names():
            # commands like `compilemessages` execute ready(), but do not
            # require a database to be present. Bail out early, if the Event
            # table has not been created yet.
            return

        try:
            for event in Event.objects.all():
                regenerate_css.apply_async(args=(event.pk,))
        except (utils.OperationalError, utils.ProgrammingError):
            pass


with suppress(ImportError):
    import pretalx.celery_app as celery  # NOQA

default_app_config = 'pretalx.common.CommonConfig'
