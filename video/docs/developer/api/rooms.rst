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
