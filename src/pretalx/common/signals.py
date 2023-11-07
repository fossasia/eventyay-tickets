import logging
import uuid
from functools import wraps
from typing import Any, Callable, List, Tuple

import django.dispatch
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.dispatch.dispatcher import NO_RECEIVERS

from pretalx.event.models import Event

app_cache = {}
logger = logging.getLogger(__name__)


def _populate_app_cache():
    apps.check_apps_ready()
    for app_config in apps.app_configs.values():
        app_cache[app_config.name] = app_config


class EventPluginSignal(django.dispatch.Signal):
    """An extension to Django's built-in signals.

    It sends out it's events only to receivers which belong to plugins
    that are enabled for the given Event.
    """

    @staticmethod
    def _is_active(sender, receiver):
        # Find the Django application this belongs to
        searchpath = receiver.__module__
        core_module = any(searchpath.startswith(cm) for cm in settings.CORE_MODULES)
        # Only fire receivers from active plugins and core modules
        if core_module:
            return True
        # Short out on events without plugins
        if sender and not sender.plugin_list:
            return False
        if sender:
            app = None
            while True:
                app = app_cache.get(searchpath)
                if "." not in searchpath or app:  # pragma: no cover
                    break
                searchpath, _ = searchpath.rsplit(".", 1)
            return app and app.name in sender.plugin_list
        return False

    def send(self, sender: Event, **named) -> List[Tuple[Callable, Any]]:
        """Send signal from sender to all connected receivers that belong to
        plugins enabled for the given Event.

        sender is required to be an instance of
        ``pretalx.event.models.Event``.
        """
        if sender and not isinstance(sender, Event):
            raise ValueError("Sender needs to be an event.")

        responses = []
        if (
            not self.receivers
            or self.sender_receivers_cache.get(sender) is NO_RECEIVERS
        ):
            return responses

        if not app_cache:
            _populate_app_cache()

        for receiver in self._live_receivers(sender):
            if self._is_active(sender, receiver):
                response = receiver(signal=self, sender=sender, **named)
                responses.append((receiver, response))
        return sorted(
            responses,
            key=lambda response: (response[0].__module__, response[0].__name__),
        )

    def send_robust(self, sender: Event, **named) -> List[Tuple[Callable, Any]]:
        """Send signal from sender to all connected receivers that belong to
        plugins enabled for the given Event. If a receiver raises an Exception,
        it is returned as the response instead of propagating.

        sender is required to be an instance of
        ``pretalx.event.models.Event``.
        """
        if sender and not isinstance(sender, Event):
            raise ValueError("Sender needs to be an event.")

        responses = []
        if (
            not self.receivers
            or self.sender_receivers_cache.get(sender) is NO_RECEIVERS
        ):
            return []

        if not app_cache:  # pragma: no cover
            _populate_app_cache()

        for receiver in self._live_receivers(sender):
            if self._is_active(sender, receiver):
                try:
                    response = receiver(signal=self, sender=sender, **named)
                except Exception as err:
                    responses.append((receiver, err))
                else:
                    responses.append((receiver, response))
        return sorted(
            responses,
            key=lambda response: (response[0].__module__, response[0].__name__),
        )

    def send_chained(
        self, sender: Event, chain_kwarg_name, **named
    ) -> List[Tuple[Callable, Any]]:
        """Send signal from sender to all connected receivers. The return value
        of the first receiver will be used as the keyword argument specified by
        ``chain_kwarg_name`` in the input to the second receiver and so on. The
        return value of the last receiver is returned by this method.

        sender is required to be an instance of
        ``pretalx.event.models.Event``.
        """
        if sender and not isinstance(sender, Event):
            raise ValueError("Sender needs to be an event.")

        response = named.get(chain_kwarg_name)
        if (
            not self.receivers
            or self.sender_receivers_cache.get(sender) is NO_RECEIVERS
        ):  # pragma: no cover
            return response

        if not app_cache:  # pragma: no cover
            _populate_app_cache()

        for receiver in self._live_receivers(sender):
            if self._is_active(sender, receiver):
                named[chain_kwarg_name] = response
                response = receiver(signal=self, sender=sender, **named)
        return response


def minimum_interval(
    minutes_after_success, minutes_after_error=0, minutes_running_timeout=30
):
    """
    Use this decorator on receivers of the ``periodic_task`` signal to ensure the receiver
    function has at least ``minutes_after_success`` minutes between two successful runs and
    at least ``minutes_after_error`` minutes between two failed runs.
    You also get a simple locking mechanism making sure the function is not called a second
    time while it is running, unless ``minutes_running_timeout`` have passed. This locking
    is naive and should not be completely relied upon.
    """

    def decorate(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key_running = f"pretalx_periodic_{f.__module__}.{f.__name__}_running"
            key_result = f"pretalx_periodic_{f.__module__}.{f.__name__}_result"

            if cache.get(key_running) or cache.get(key_result):
                return

            uniqid = str(uuid.uuid4())
            cache.set(key_running, uniqid, timeout=minutes_running_timeout * 60)
            try:
                retval = f(*args, **kwargs)
            except Exception as e:
                try:
                    cache.set(key_result, "error", timeout=minutes_after_error * 60)
                except Exception:
                    logger.exception("Could not store result")
                raise e
            else:
                try:
                    cache.set(key_result, "success", timeout=minutes_after_success * 60)
                except Exception:
                    logger.exception("Could not store result")
                return retval
            finally:
                try:
                    if cache.get(key_running) == uniqid:
                        cache.delete(key_running)
                except Exception:
                    logger.exception("Could not release lock")

        return wrapper

    return decorate


periodic_task = django.dispatch.Signal()
"""
This is a regular django signal (no pretalx event signal) that we send out every
time the periodic task cronjob runs. This interval is not sharply defined, it can
be everything between a minute and a day. The actions you perform should be
idempotent, meaning it should not make a difference if this is sent out more often
than expected.
"""

register_data_exporters = EventPluginSignal()
"""
This signal is sent out to get all known data exporters. Receivers should return a
subclass of pretalx.common.exporter.BaseExporter

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
"""
activitylog_display = EventPluginSignal()
"""
To display an instance of the ``ActivityLog`` model to a human user,
``pretalx.common.signals.activitylog_display`` will be sent out with an ``activitylog``
argument.

The first received response that is not ``None`` will be used to display the log entry
to the user. The receivers are expected to return plain (lazy) text.

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
"""
activitylog_object_link = EventPluginSignal()
"""
To display the relationship of an instance of the ``ActivityLog`` model to another model
to a human user, ``pretalx.common.signals.activitylog_object_link`` will be sent out
with an ``activitylog`` argument.

The first received response that is not ``None`` will be used to display the related object
to the user. The receivers are expected to return an HTML link as a string.
Make sure that any user content in the HTML code you return is properly escaped!

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""
register_locales = django.dispatch.Signal()
"""
To provide additional languages via plugins, you will have to provide some settings in
the pretalx settings file, and return a list of the registered locales as response
to this plugin signal. Every entry should be a tuple of two strings, the first being
the locale code, the second being the display name of the locale. (Though pretalx will
also accept just a locale code.)

You should always return your locale when no ``sender`` keyword argument is given to
make your locale available to the makemessages command. Otherwise, check that your
plugin is enabled in the current event context if your locale should be scoped to
events with your plugin activated.
"""
