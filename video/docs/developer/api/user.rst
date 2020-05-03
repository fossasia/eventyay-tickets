User/Account handling
=====================

Users can be authenticated in two ways:

* With a ``client_id`` that uniquely represents a browser. This is usually used as a form of guest access for events
  that do not require prior registration.

* With a ``token`` that has been created by an external system (such as an event registartion system) that identifies
  and grants specific rights.

Logging in
----------

Send client-specific ID, receive everything that's already known about the user::

    => ["authenticate", {"client_id": "UUID4"}]
    <- ["authenticated", {"user.config": {…}, "world.config": {…}, "chat.channels": []}]

With a token, it works just the same way::

    => ["authenticate", {"token": "JWTTOKEN"}]
    <- ["authenticated", {"user.config": {…}, "world.config": {…}, "chat.channels": []}]

``chat.channels`` contains a list of **non-volatile** chat rooms the user is a member of. See chat module
documentation for membership semantics.

Change user info
----------------

You can change a user's profile using the ``user.update`` call::

    => ["user.update", 123, {"profile": {…}}]
    <- ["success", 123, {}]

Receiving info on another user
------------------------------

You can fetch the profile for a specific user by their ID::

    => ["user.fetch", 123, {"id": "1234"}]
    <- ["success", 123, {"id": "1234", "profile": {…}}]

If the user is unknown, error code ``user.not_found`` is returned.

Profile updates
---------------

If your user data changes, you will receive a broadcast with your new profile. This is e.g. important if your profile
is changed from a different connection::

    <= ["user.updated", {"id": "1234", "profile": {…}}]
