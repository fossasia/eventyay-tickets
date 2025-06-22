Roulette module
===============

The roulette module allows to create random video pairings between attendees.

Handshake
---------

To request a video chat with an arbitrary user, a client can push a message like this::

    => ["roulette.start", 1234, {"room": "room_1"}]

If there's already another person waiting the user can instantly be connected to, the server responds with::

    <- ["success", 1234, {"status": "match", "other_user": {…}, "call_id": "…"}]

If there isn't, the server registers the request and replies like this::

    <- ["success", 1234, {"status": "wait"}]

Requests are valid for 30 seconds, the client should send a new ``roulette.start`` request every 15-25 seconds. The
server may either respond with ``status: match`` to one of these, or the server sends a notification:

    <- ["roulette.match_found", {"other_user": {…}, "call_id": "…"}]

This way, both matched users end up with the same ``call_id`` that can be used to request Janus video call parameters
for the same call::

    => ["januscall.roulette_url", 1234, {"call_id": "…"}]
    <- ["success", 1234, {"server": "…", "roomId": "…", "token: "…", "iceServers": []}]

If the client wants to quit while in ``status: wait`` state, the client should send a stop request::

    => ["roulette.stop", 1234, {"room_id": "room_1"}]
    <- ["success", 1234, {}]

Hangup
------

If one person wants to hang up, they can send::

    => ["roulette.hangup", 1234, {"call_id": "…"}]
    <- ["success", 1234, {}]

The other person will receive the following message::

    <- ["roulette.hangup", {}]

.. _Janus: https://janus.conf.meetecho.com/