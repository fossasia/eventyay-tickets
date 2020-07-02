Rooms
=====

Users with sufficient :ref:`permissions` can take world-relevant actions like create rooms.

Room navigation
---------------

Rooms can be entered like this::

    => ["room.enter", 123, {"room": "room_1"}]
    <- ["success", 123, {}]

And left like this::

    => ["room.leave", 123, {"room": "room_1"}]
    <- ["success", 123, {}]

Notifying the server of the rooms you enter and leave is important for statistical purposes, such as showing the viewer
count of a room, but also to make sure you receive room-level events such as reactions.

Reactions
---------

You can send a reaction like this::

    => ["room.react", 123, {"room": "room_1", "reaction": "clap"}]
    <- ["success", 123, {}]

You will get a success message even if the reaction is ignored due to rate limiting.

If you or someone else reacts, you receive aggregated reaction events, approximately one per second::

    <= ["room.reaction", {"room": "room_1", "reactions": {"clap": 42, "+1": 12}}]

Allowed reactions currently are:

* ``clap``
* ``+1``
* ``open_mouth``
* ``heart``

Room management
---------------

You can delete a room like this::

    => ["room.delete", 123, {"room": "room_1"}]
    <- ["success", 123, {}]


As an administrator, you can also get a room's internal configuration::

    => ["room.config.get", 123, {"room": "room_1"}]
    <- ["success", 123, {…}]


And update it::

    => ["room.config.patch", 123, {"room": "room_1", "name": "Bla"}]
    <- ["success", 123, {…}]

Or for all rooms::

    => ["room.config.list", 123, {}]
    <- ["success", 123, [{…}, …]]

Schedule changes
----------------

Moderators can update the current ``schedule_data`` field like this::

    => ["room.schedule", 123, {"room": "room_1", "schedule_data": {"session": 1}}]
    <- ["success", 123, {}]

Permitted session data keys are ``session`` and ``title``.

When the schedule data is updated, a broadcast to all users in the room is sent::

    => ["room.schedule", {"room": "room_1", "schedule_data": {"session": 1}}]
