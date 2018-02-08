from typing import Any, Callable, List, Tuple

import django.dispatch
from django.apps import apps
from django.conf import settings
from django.dispatch.dispatcher import NO_RECEIVERS

from pretalx.event.models import Event

app_cache = {}


def _populate_app_cache():
    global app_cache
    apps.check_apps_ready()
    for ac in apps.app_configs.values():
        app_cache[ac.name] = ac


class EventPluginSignal(django.dispatch.Signal):
    """
    This is an extension to Django's built-in signals which differs in a way that it sends
    out it's events only to receivers which belong to plugins that are enabled for the given
    Event.
    """

    def _is_active(self, sender, receiver):
        if sender is None:
            # Send to all events!
            return True

        # Find the Django application this belongs to
        searchpath = receiver.__module__
        core_module = any([searchpath.startswith(cm) for cm in settings.LOCAL_APPS])
        app = None
        if not core_module:
            while True:
                app = app_cache.get(searchpath)
                if "." not in searchpath or app:
                    break
                searchpath, _ = searchpath.rsplit(".", 1)

        # Only fire receivers from active plugins and core modules
        if core_module or (sender and app and app.name in sender.get_plugins()):
            return True
        return False

    def send(self, sender: Event, **named) -> List[Tuple[Callable, Any]]:
        """
        Send signal from sender to all connected receivers that belong to
        plugins enabled for the given Event.

        sender is required to be an instance of ``pretalx.event.models.Event``.
        """
        if sender and not isinstance(sender, Event):
            raise ValueError("Sender needs to be an event.")

        responses = []
        if not self.receivers or self.sender_receivers_cache.get(sender) is NO_RECEIVERS:
            return responses

        if not app_cache:
            _populate_app_cache()

        for receiver in self._live_receivers(sender):
            if self._is_active(sender, receiver):
                response = receiver(signal=self, sender=sender, **named)
                responses.append((receiver, response))
        return sorted(responses, key=lambda r: (receiver.__module__, receiver.__name__))

    def send_chained(self, sender: Event, chain_kwarg_name, **named) -> List[Tuple[Callable, Any]]:
        """
        Send signal from sender to all connected receivers. The return value of the first receiver
        will be used as the keyword argument specified by ``chain_kwarg_name`` in the input to the
        second receiver and so on. The return value of the last receiver is returned by this method.

        sender is required to be an instance of ``pretalx.event.models.Event``.
        """
        if sender and not isinstance(sender, Event):
            raise ValueError("Sender needs to be an event.")

        response = named.get(chain_kwarg_name)
        if not self.receivers or self.sender_receivers_cache.get(sender) is NO_RECEIVERS:
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
idempotent, i.e. it should not make a difference if this is sent out more often
than expected.
"""

event_live_issues = EventPluginSignal(
    providing_args=[]
)
"""
This signal is sent out to determine whether an event can be taken live. If you want to
prevent the event from going live, return a string that will be displayed to the user
as the error message. If you don't, your receiver should return ``None``.

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
"""


register_data_exporters = EventPluginSignal(
    providing_args=[]
)
"""
This signal is sent out to get all known data exporters. Receivers should return a
subclass of pretix.base.exporter.BaseExporter

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
"""

entry_submitted = EventPluginSignal(
    providing_args=['submission']
)
"""
This signal is sent out every time an entry is submitted. The submission object is given
as the first argument. This signal is also sent out if the submission has been added
for the speaker by an organiser, so take care to handle that case, aswell.

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
"""

submission_accepted = EventPluginSignal(
    providing_args=['submission']
)
"""
This signal is sent out every time as submission is accepted. The submission object is given
as the first argument.

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
"""

submission_rejected = EventPluginSignal(
    providing_args=['submission']
)
"""
This signal is sent out every time as submission is rejected. The submission object is given
as the first argument.

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
"""

submission_confirmed = EventPluginSignal(
    providing_args=['submission']
)
"""
This signal is sent out every time as submission is confirmed. The submission object is given
as the first argument.

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
"""

logentry_display = EventPluginSignal(
    providing_args=["logentry"]
)
"""
To display an instance of the ``LogEntry`` model to a human user,
``pretalx.common.signals.logentry_display`` will be sent out with a ``logentry`` argument.

The first received response that is not ``None`` will be used to display the log entry
to the user. The receivers are expected to return plain text.

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
"""

register_global_settings = django.dispatch.Signal()
"""
All plugins that are installed may send fields for the global settings form, as
an OrderedDict of (setting name, form field).
"""

email_filter = EventPluginSignal(
    providing_args=['message', 'submission']
)
"""
This signal allows you to implement a middleware-style filter on all outgoing emails. You are expected to
return a (possibly modified) copy of the message object passed to you.

As with all event plugin signals, the ``sender`` keyword argument will contain the event.
The ``message`` argument will contain an ``EmailMultiAlternatives`` object.
If the email is associated with a specific submission, the ``submission`` argument will be passed as well,
otherwise it will be ``None``.
"""
