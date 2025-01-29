from pretix.base.signals import EventPluginSignal

nav_event_common = EventPluginSignal()
"""
Arguments: ``request``

This signal allows you to add additional views to the common sidebar navigation.
You will get the request as a keyword argument ``request``.
Receivers are expected to return a list of dictionaries. The dictionaries
should contain at least the keys ``label`` and ``url``. You can also return
a fontawesome icon name with the key ``icon``, it will be respected depending
on the type of navigation. You should also return an ``active`` key with a boolean
set to ``True``, when this item should be marked as active. The ``request`` object
will have an attribute ``event``.

You can optionally create sub-items to create hierarchical navigation. There are two
ways to achieve this: Either you specify a key ``children`` on your top navigation item
that contains a list of navigation items (as dictionaries), or you specify a ``parent``
key with the ``url`` value of the designated parent item.
The latter method also allows you to register navigation items as a sub-item of existing ones.

If you use this, you should read the documentation on :ref:`how to deal with URLs <urlconf>`
in pretix.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
"""