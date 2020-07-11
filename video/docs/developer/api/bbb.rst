BigBlueButton module
====================

Message flow
------------

To join the video chat for a room, a client can push a message like this::

    => ["bbb.room_url", 1234, {"room": "room_1"}]
    <- ["success", 1234, {"url": "https://…"}]
    
The response will contain an URL for the video chat. A display name needs to be set, otherwise
an error of type ``bbb.join.missing_profile`` is returned. If the BBB server can't be reached, ``bbb.failed`` is
returned.
