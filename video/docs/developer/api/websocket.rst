Websocket connection
====================

The internal API is currently exclusively spoken over a long-standing websocket connection between the client and the
server. The URL of the websocket endpoint is ``wss://<hostname>/ws/world/<worldid>``.

We use a JSON-based message protocal on the websocket.
On the root level, we use an array structure that is built like this::

    [$ACTION_NAME, ($SEQUENCE_NUMBER or $COMMAND_ID), $PAYLOAD]
    ["ping", 1501676765]
    ["ot", 4953, {"variant": 103, "ops":[{"retain": 5}, {"insert": "foobar"}]}]

Generic RPC
-----------

Unless otherwise noted, all acctions annotated with ``<==>`` in this documentation, use the following communication
style.

Success case::

    => [$ACTION_NAME, $CORRELATION_ID, $PAYLOAD]
    <- ["success", $CORRELATION_ID, $UPDATE_OR_RESULT]
    <≈ [$ACTION_NAME, $UPDATE_OR_RESULT]

Error case::

    => [$ACTION_NAME, $CORRELATION_ID, $PAYLOAD]
    <- ["error", $CORRELATION_ID, $ERROR_PAYLOAD]

In this documentation, ``<-`` means the message is sent *only* to the original client, and
``<≈`` denotes a broadcast to all other clients. ``=>`` represents a message to the server.

Keepalive
---------

Since WebSocket ping-pong is not exposed to JavaScript, we have to build our own on top::

    ["ping", $TIMESTAMP]
    ["pong", $SAME_TIMESTAMP]

Connection management
---------------------

After you established your connection, it's your job to send an authentication message.
If you connected to an invalid endpoint, however, you will receive a message like
this::

    <- ["error", {"code": "world.unknown_world"}]

The server can at any time drop the connection unexpected, in which case you should
retry. If the server drops the connection due to an unexpected error in the server,
you receive a message like this::

    <- ["error", {"code": "server.fatal"}]

If the server would like you to reload the client code, you get a message like this::

    <- ["connection.reload", {}]

If the server would like you to disconnect because the user opened too many new connections, you get a message like
this::

    <- ["error", {"code": "connection.replaced"}]
