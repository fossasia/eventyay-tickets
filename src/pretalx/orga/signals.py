from django.dispatch import Signal

from pretalx.common.signals import EventPluginSignal

nav_event = EventPluginSignal(providing_args=["request"])
"""
This signal allows you to add additional views to the admin panel
navigation. You will get the request as a keyword argument ``request``.
Receivers are expected to return a list of dictionaries. The dictionaries
should contain at least the keys ``label`` and ``url``. You can also return
a ForkAwesome icon name with the key ``icon``, it will  be respected depending
on the type of navigation. You should also return an ``active`` key with a boolean
set to ``True``, when this item should be marked as active. The ``request`` object
will have an attribute ``event``.

If you use this, you should read the documentation on :ref:`how to deal with URLs <urlconf>`
in pretalx.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
"""
nav_global = Signal(providing_args=["request"])
"""
This signal allows you to add additional views to the navigation bar when no event is
selected. You will get the request as a keyword argument ``request``.
Receivers are expected to return a list of dictionaries. The dictionaries
should contain at least the keys ``label`` and ``url``. You can also return
a ForkAwesome icon name with the key ``icon``, it will  be respected depending
on the type of navigation. You should also return an ``active`` key with a boolean
set to ``True``, when this item should be marked as active.

If you use this, you should read the documentation on :ref:`how to deal with URLs <urlconf>`
in pretalx.

This is no ``EventPluginSignal``, so you do not get the event in the ``sender`` argument
and you may get the signal regardless of whether your plugin is active.
"""
activate_event = EventPluginSignal(providing_args=["request"])
"""
This signal is sent out before an event goes live. It allows any installed
plugin to raise an Exception to prevent the event from going live. The
exception message will be exposed to the user.
You will get the request as a keyword argument ``request``.
Receivers are not expected to return a response.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
"""
nav_event_settings = EventPluginSignal(providing_args=["request"])
"""
This signal is sent out to collect additional settings sub-pages of an event.
Receivers are expected to return a list of dictionaries. The dictionaries
should contain at least the keys ``label`` and ``url``. You should also return
an ``active`` key with a boolean set to ``True``, when this item should be marked
as active.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
A second keyword argument ``request`` will contain the request object.
"""
event_copy_data = EventPluginSignal(
    providing_args=["other", "question_map", "track_map", "submission_type_map"]
)
"""
This signal is sent out when a new event is created as a clone of an existing event, i.e.
the settings from the older event are copied to the newer one. You can listen to this
signal to copy data or configuration stored within your plugin's models as well.

You don't need to copy data inside the general settings storage which is cloned automatically,
but you might need to modify that data.

The ``sender`` keyword argument will contain the event of the **new** event. The ``other``
keyword argument will contain the event slug to **copy from**. The keyword arguments
``submission_type_map``, ``question_map``, and ``track_map`` contain
mappings from object IDs in the original event to objects in the new event of the respective
types.
"""
