Websocket wire protocol
=======================

We use a JSON-based messages on the websocket.
On the root level, we use an array structure that is used like this:

    [$ACTION_NAME, ($SEQUENCE_NUMBER or $COMMAND_ID), $PAYLOAD]
    ["ping", 1501676765]
    ["ot", 4953, {"variant": 103, "ops":[{"retain": 5}, {"insert": "foobar"}]}]

Sequence numbers / error handling
---------------------------------

This generic form of RPC-style calls is used for all actions annotated with ``<=>`` unless otherwise noted:
Success case:

    => [$ACTION_NAME, $CORRELATION_ID, $PAYLOAD]
    <- ['success', $CORRELATION_ID, $UPDATE_OR_RESULT]
    <≈ [$ACTION_NAME, $UPDATE_OR_RESULT]
    
Error case:

    => [$ACTION_NAME, $CORRELATION_ID, $PAYLOAD]
    <- ['error', $CORRELATION_ID, $ERROR_PAYLOAD]
    
where ``<-`` means the message is sent *only* to the original client, and
``<≈`` denotes a broadcast to all other clients.
