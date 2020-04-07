# Chat module

## Message flow

To join the chat for a room, a client can push a message like this:

    => ["chat.join", 1234, {"room": "room_0"}]
    <- ["success", 1234, {}]

The room can be left the same way:

    => ["chat.leave", 1234, {"room": "room_0"}]
    <- ["success", 1234, {}]

To send a simple text message:

    => ["chat.send", 1234, {"room": "room_0", "event_type": "message", "content": {"type": "text", "body": "Hello world"}}]
    <- ["success", 1234, {}]

All clients in the room, including the client who sent the message itself, will get a broadcast:

    <= ["chat.event", {"room": "room_0", "event_type": "message", "content": {"type": "text", "body": "Hello world"}, "sender": "user_todo", "event_id": 4}]
   
## Event types

The only relevant data structure in the chat are "events", that are being passed back and forth between client and
server. All events have the following properties:

* ``room`` (string)
* ``event_type`` (string)
* ``content`` (depending on ``event_type``)

Currently, the following types of events are defined:


### Messages

Event type ``message`` represents a message sent from a user to the chat room. It has the following properties:

* ``type``: Content Type (string)
* ``body``: Content (depending on ``type``)

Currently, the following types are defined:

* ``text``: A plain text message. ``body`` is a string with the message.
