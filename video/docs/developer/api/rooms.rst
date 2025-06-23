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

Viewers
-------

If you have the ``room:viewers`` permission, you will also receive a list of users currently in this room (not for all room types)::

    => ["room.enter", 123, {"room": "room_1"}]
    <- ["success", 123, {"viewers": [{"id": "…", "profile": {…}, …}]}]

If another viewer enters, you will receive a broadcast. Note that you are expected to do de-duplication of viewer IDs
on the client side as well for safety as you could receive multiple events for the same person if they join with multiple
browsers::

    <= ["room.viewer.added", {"user": {"id": "…", "profile": {…}, …}}]

When a viewer leave, you will also get a broadcast with just the user ID (as you won't need the full profile any more)::

    <= ["room.viewer.removed", {"user_id": "…"}]

Reactions
---------

You can send a reaction like this::

    => ["room.react", 123, {"room": "room_1", "reaction": "👏"}]
    <- ["success", 123, {}]

You will get a success message even if the reaction is ignored due to rate limiting.

If you or someone else reacts, you receive aggregated reaction events, approximately one per second::

    <= ["room.reaction", {"room": "room_1", "reactions": {"👏": 42, "👍": 12}}]

Allowed reactions currently are:

* ``👏``
* ``❤️``
* ``👍``
* ``🤣``
* ``😮``

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

Reorder rooms::

    => ["room.config.reorder", 123, [$id, $id2, $id3…]]
    <- ["success", 123, [{…}, …]]

Schedule changes
----------------

Moderators can update the current ``schedule_data`` field like this::

    => ["room.schedule", 123, {"room": "room_1", "schedule_data": {"session": 1}}]
    <- ["success", 123, {}]

Permitted session data keys are ``session`` and ``title``.

When the schedule data is updated, a broadcast to all users in the room is sent::

    => ["room.schedule", {"room": "room_1", "schedule_data": {"session": 1}}]

Anonymous invites
-----------------

Admins (or kiosk users) can retrieve an invite link that can be used by in-person attendees of the event to join the Q&A or polls for a specific room without needing to create a full user profile::

    => ["room.invite.anonymous.link", 123, {"room": "room_1"}]
    <- ["success", 123, {"url": "https://vnls.io/kLeNv6"}]
