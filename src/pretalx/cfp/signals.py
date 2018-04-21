from pretalx.common.signals import EventPluginSignal

footer_link = EventPluginSignal(
    providing_args=["request"]
)
"""
This signal allows you to add links to the footer of an event page. You are
expected to return a dictionary containing the keys ``label`` and ``url``.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
"""
