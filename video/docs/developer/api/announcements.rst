Announcements module
====================

The announcements module allows organisers to push announcements to all users.

Creating or updating an announcement
------------------------------------

To create an announcement, a user with the permission ``WORLD_ANNOUNCE`` sends
a message like this::

    => ["announcement.create", 1234, {"text": "Announcement text", "show_until": "timestamp or null", "state": "active"}]
    <- ["success", 1234, {"announcement": []}]

Announcements can have an expiry timestamp (``show_until``), or can be
deactivated manually by the administrators by setting its state from ``active``
to ``archived``. Optionally, the state can be ``draft`` before it is
``active``. Only these two state transitions (``draft`` to ``active``,
``active`` to ``archived``) are permitted.

To update an announcement, include its ``id`` and send an
``announcement.update`` message.

Receiving announcements
-----------------------

Announcements are always sent out with a ``created_or_updated`` message::

    <= ["announcement.created_or_updated", {"id": "", "text": "", "show_until": "", "state": "active"}]

Additionally, all currently visible announcements are listed in the initial
response after authenticating, as the ``"announcements"`` field.

List announcements
------------------

To receive a list of all available announcements::

    => ["announcement.list", 1234, {}]
    <- ["success", 1234, []]
