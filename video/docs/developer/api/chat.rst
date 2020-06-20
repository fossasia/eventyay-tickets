Chat module
===========

Membership and subscription
---------------------------

There's two concepts that need to be viewed separately:

* **Membership** is an relationship between an **user** and a channel. Membership of a channel is publicly visible.

* **Subscription** is an relationship between a **client** and a channel. Subscription is not publicly visible.

You can be a member without being subscribed, for example when you joined a chat room and then closed your browser.
You can also be subscribed without being a member, for example when reading a public chat without actively
participating.

In some channels, membership is **volatile**. This means that members automatically *leave* the channel if they no
longer have any subscribed clients.

Every user can either be a member of a channel or not, while a user can have multiple subscriptions to a channel, e.g.
if they use the application in multiple browser tabs.

To become a member, a client can push a **join** message::

    => ["chat.join", 1234, {"channel": "room_0"}]
    <- ["success", 1234, {"state": {…}, "next_event_id": 54321, "members": []}]

A join means that the user and their chosen ``profile`` will be visible to other users.
Messages can only be sent to chats that have been joined. A join action is **implicitly also a subscribe** action.
Joins are idempotent, joining a channel that the user is already part of will not return an error.

After a join or leave, your current membership list of non-volatile channels will be broadcasted to all clients of that user for synchronization::

    <= ["chat.channels", {"channels": [{"id": "room_0", "notification_pointer": 12345}]}]

The room can be left the same way::

    => ["chat.leave", 1234, {"channel": "room_0"}]
    <- ["success", 1234, {}]

The leave action is **implicitly also an unsubscribe** action. 

If you don't want to join or leave, you can explicitly subscribe and unsubscribe::

    => ["chat.subscribe", 1234, {"channel": "room_0"}]
    <- ["success", 1234, {"state": {…}, "next_event_id": 54321, "members": []}]
    => ["chat.unsubscribe", 1234, {"channel": "room_0"}]
    <- ["success", 1234, {}]

If you close the websocket, an unsubscribe will be performed automatically.

Events
------

Everything that happens within chat, is an *event*. For example, if a user sends a message, you will receive an event
like this::

    <= ["chat.event", {"channel": "room_0", "event_type": "channel.message", "content": {"type": "text", "body": "Hello world"}, "sender": "user_todo", "event_id": 4}]
    
The different event types are described below. After you joined a channel, the first event you see will be a membership
event announcing your join. If you want to fetch previous events, you can do so with the ``chat.fetch`` command. As
a base point, you can use the ``next_event_id`` from the reply to ``chat.subscribe`` or ``chat.leave``. This is built
in a way that if events happen *while* you join, you might see the same event *twice*, but you will not miss any events::

    => ["chat.fetch", 1234, {"channel": "room_0", "count": 30, "before_id": 54321}]
    <- ["success", 1234, {"results": […]}]

In volatile chat rooms, ``chat.fetch`` will skip membership messages (joins/leaves).

To send a simple text message::

    => ["chat.send", 1234, {"channel": "room_0", "event_type": "channel.message", "content": {"type": "text", "body": "Hello world"}}]
    <- ["success", 1234, {"event": {"channel": "room_0", "event_type": "channel.message", "content": {"type": "text", "body": "Hello world"}, "sender": "user_todo", "event_id": 4}}]

All clients in the room will get a broadcast (see above). Currently, you will get the broadcast as well, so you should
not show the chat message twice, but you also shouldn't rely on getting the broadcast since it might be removed in
the future as a performance optimization.

You can edit a user's own message by sending an update like this::

    => ["chat.send", 1234, {"channel": "room_0", "event_type": "channel.message", "replaces": 2000, "content": {"type": "text", "body": "Hello world"}}]
    <- ["success", 1234, {"event": {"channel": "room_0", "event_type": "channel.message", "replaces": 2000, "content": {"type": "text", "body": "Hello world"}, "sender": "user_todo", "event_id": 4}}]

As with message sending, you'll get both the success and the broadcast. The broadcast looks the same as a new message,
only that it includes the ``"replaces"`` key.

Event types
^^^^^^^^^^^

The only relevant data structure in the chat are "events", that are being passed back and forth between client and
server. All events have the following properties (plus additional ones depending on event type):

* ``channel`` (string)
* ``event_type`` (string)
* ``sender`` (string, user ID, optional)
* ``content`` (type and value depending on ``event_type``)

Currently, the following values for ``event_type`` are defined:

- ``channel.message``
- ``channel.member``

Optional fields include:

- ``replaces``, only valid on ``event_type: channel.message``, indicates that the current message supersedes a previous one.

``channel.message``
"""""""""""""""""""

Event type ``channel.message`` represents a message sent from a user to the chat room. It has the following properties
inside the ``content`` property:

* ``type``: Content Type (string)
* ``body``: Content (depending on ``type``)

Currently, the following types are defined:

* ``text``: A plain text message. ``body`` is a string with the message.
* ``deleted``: Any message that was removed by the user or a moderator.

``channel.member``
""""""""""""""""""

This message type is used:

- When a user joins a channel.
  If the user has no ``profile`` yet, an error with the code ``channel.join.missing_profile`` is returned.
- When a user leaves a channel
- When a user is kicked/banned

When a user joins or leaves a channel, an event is sent to all current subscribers of the channel. It contains the
following properties inside the ``content`` property:

- ``membership``: "join" or "leave" or "ban"
- ``user``: A dictionary of user data of the user concerned (i.e. the user joining or leaving or being banned)

Read/unread status
------------------

During authentication, the backend sends you two chat-related keys in the authentication response::

    "chat.channels": [
        {
            "id": "room_0",
            "notification_pointer": 1234,
        },
        {
            "id": "room_2",
            "notification_pointer": 1337,
        },
    ],
    "chat.read_pointers": {
        "room_0": 1234
    },

This tells you that the user has an active, non-volatile membership in two channels (``room_0`` and ``room_1``) and the
event IDs of the last events that happened in these two channels ("notification pointer". Additionally, it tells you
that the user has read all messages the first room (the read pointer is equal to the notification pointer), while
they haven't read any message in the second room.

Once the user has read the new messages in ``room_2``, you can confirm this to the server like this::

    => ["chat.mark_read", 1234, {"channel": "room_2", "id": 1337}]
    <- ["success", 1234, {}}]

All other connected clients of the same user get an updated list of read pointers::

    <= ["chat.read_pointers", {"room_0": 1234, "room_2": 1337}}]

The client should use the pointers to *update* the local state, but may not rely on all channels to be included in the
list, even though the backend implementation always sends all channels.

If, in the meantime, a new message is written in the first room, you will receive a broadcast that includes the new
notification pointer::

    <= ["chat.notification_pointers", {"room_0": 1400}}]

Important notes:

* Again, the message may not contain all channels that you are a member of, only those with a changed value.

* Whenever the notification pointer in the client's known state is larger than the read pointer, the channel should be
  indicated to the user as containing unread messages.

* You won't receive a notification pointer update with every message. If the server knows the notification pointer
  already is larger than your read pointer, it may skip the update since it does not change the user-visible result.

* The server may or may not omit these updates for non-content messages, such as leave and join messages.

* The server may or may not omit these updates for channels you are currently subscribed to, since you receive these
  events anyways.

* The client should ignore notification pointers with lower values than the last known notification pointers.

* These broadcasts are **not** send for volatile memberships.
