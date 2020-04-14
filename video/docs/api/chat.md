# Chat module

## Message flow

To join the chat for a room, a client can push a message like this:

    => ["chat.join", 1234, {"channel": "room_0"}]
    <- ["success", 1234, {}]

A join means that the user and their chosen `profile` will be visible to other users.
The room can be left the same way:

    => ["chat.leave", 1234, {"channel": "room_0"}]
    <- ["success", 1234, {}]

Separate from joining, a chat can also be subscribed and unsubscribed.

    => ["chat.subscribe", 1234, {"channel": "room_0"}]
    <- ["success", 1234, {"state": {…}, "members": []}]
    => ["chat.unsubscribe", 1234, {"channel": "room_0"}]
    <- ["success", 1234, {}]

Messages can only be sent to chats that have been joined. A join action is implicitly also a subscribe action. An
unsubscribe action is implicitly also a leave action.

To send a simple text message:

    => ["chat.send", 1234, {"channel": "room_0", "event_type": "channel.message", "content": {"type": "text", "body": "Hello world"}}]
    <- ["success", 1234, {}]

All clients in the room, including the client who sent the message itself, will get a broadcast:

    <= ["chat.event", {"channel": "room_0", "event_type": "channel.message", "content": {"type": "text", "body": "Hello world"}, "sender": "user_todo", "event_id": 4}]

## Event types

The only relevant data structure in the chat are "events", that are being passed back and forth between client and
server. All events have the following properties (plus additional ones depending on event type):

* ``channel`` (string)
* ``event_type`` (string)
* ``sender`` (string, user ID, optional)

Currently, the following types of events are defined:

- ``channel.message``
- ``channel.member``


### ``channel.message``

Event type ``channel.message`` represents a message sent from a user to the chat room. It has the following properties
inside the ``content`` property:

* ``type``: Content Type (string)
* ``body``: Content (depending on ``type``)

Currently, the following types are defined:

* ``text``: A plain text message. ``body`` is a string with the message.

### ``channel.member``

This message type is used:

- When a user joins a channel.
  If the user has no ``profile`` yet, an error with the code ``channel.join.missing_profile`` is returned.
- When a user leaves a channel
- When a user is kicked/banned

When a user joins or leaves a channel, an event is sent to all current subscribers of the channel. It contains the
following properties:

- ``membership``: "join" or "leave" or "ban"
- ``user``: A dictionary of user data of the user concerned (i.e. the user joining or leaving or being banned)
