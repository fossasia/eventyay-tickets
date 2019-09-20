from typing import Any, Callable, List, Tuple

import django.dispatch
from django.apps import apps
from django.conf import settings
from django.dispatch.dispatcher import NO_RECEIVERS

from pretalx.event.models import Event

app_cache = {}


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
        core_module = any([searchpath.startswith(cm) for cm in settings.CORE_MODULES])
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
                if "." not in searchpath or app:
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

        if not app_cache:
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

    def send_chained(self, sender: Event, chain_kwarg_name, **named) -> List[Tuple[Callable, Any]]:
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
        ):
            return response

        if not app_cache:
            _populate_app_cache()

        for receiver in self._live_receivers(sender):
            if self._is_active(sender, receiver):
                named[chain_kwarg_name] = response
                response = receiver(signal=self, sender=sender, **named)
        return response


periodic_task = django.dispatch.Signal()
"""
This is a regular django signal (no pretalx event signal) that we send out every
time the periodic task cronjob runs. This interval is not sharply defined, it can
be everything between a minute and a day. The actions you perform should be
idempotent, meaning it should not make a difference if this is sent out more often
than expected.
"""

register_data_exporters = EventPluginSignal(providing_args=[])
"""
This signal is sent out to get all known data exporters. Receivers should return a
subclass of pretalx.common.exporter.BaseExporter

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
"""
