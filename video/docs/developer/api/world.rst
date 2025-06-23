World actions
=============

Users with sufficient :ref:`permissions` can take world-relevant actions like create rooms.

Room creation
-------------

Rooms can be created with

    <= ["room.create", { … }]

The body of the room is structured like this:


.. code-block:: json

    {
        "name": "Neuer Raum",
        "modules": [],
        "permission_preset": "public",
        "announcements": []
    }


The content of ``modules`` can be any list of objects just like in the :ref:`world-config`,
though only the presence of ``{"type": "chat.native"}`` will currently be processed by the server.

All users will receive a complete ``room.create`` message. The payload is the same as a room object in the world config.

Additionally, the requesting user will receive a success response in the form

.. code-block:: json

    {
        "room": "room-id-goes-here",
        "channel": "channel-id-goes-here-if-appropriate"
    }


World configuration
-------------------

As an administrator, you can also get a world's internal configuration::

    => ["world.config.get", 123, {}]
    <- ["success", 123, {…}]


And update it::

    => ["world.config.patch", 123, {"title": "Bla"}]
    <- ["success", 123, {…}]
