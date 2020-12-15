Roulette module
===============

The roulette module allows to create random video pairings between attendees.

Start a call
------------

To start a video chat with an arbitrary user, a client can push a message like this::

    => ["roulette.start", 1234, {"room": "room_1"}]
    <- ["success", 1234, {"server": "https://…", "roomId": "…", "token": "…"}]

The parameters from the response can be used to connect to a `Janus`_ video room. You might be the only one in the
room until someone else joins.


.. _Janus: https://janus.conf.meetecho.com/