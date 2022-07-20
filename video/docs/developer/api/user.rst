User/Account handling
=====================

Users can be authenticated in two ways:

* With a ``client_id`` that uniquely represents a browser. This is usually used as a form of guest access for events
  that do not require prior registration.

* With a ``token`` that has been created by an external system (such as an event registartion system) that identifies
  and grants specific rights.

Logging in
----------

The first message you send should be an authentication request. Before you do so, you
will also not get any messages from the server, except for an error with the code
``world.unknown_world`` if you connected to an invalid websocket endpoint or possibly
a ``connection.reload`` message if your page load interferes with an update of the
client codebase.

Send client-specific ID, receive everything that's already known about the user::

    => ["authenticate", {"client_id": "UUID4"}]
    <- ["authenticated", {"user.config": {…}, "world.config": {…}, "chat.channels": [], "chat.read_pointers": {}}]

With a token, it works just the same way::

    => ["authenticate", {"token": "JWTTOKEN"}]
    <- ["authenticated", {"user.config": {…}, "world.config": {…}, "chat.channels": [], "chat.read_pointers": {}}]

``chat.channels`` contains a list of **non-volatile** chat rooms the user is a member of. See chat module
documentation for membership semantics.

If authentication failes, you receive an error instead::

    => ["authenticate", {"client_id": "UUID4"}]
    <- ["error", {"code": "auth.invalid_token"}]

The following error codes are currently used during authentication:

* ``auth.missing_id_or_token``
* ``auth.invalid_token``
* ``auth.missing_token``
* ``auth.expired_token``
* ``auth.denied``

User objects
------------

User objects currently contain the following properties:

* ``id``
* ``profile``
* ``pretalx_id`` (string) Only set on speakers added by pretalx or other scheduling tools
* ``badges`` list of user-visible badges to show for this user (i.e. "orga team member")
* ``moderation_state`` (``""``, ``"silenced"``, or ``"banned"``). Only set on *other* users' profiles if you're allowed
  to perform silencing and banning.
* ``inactive`` set to ``true`` if the user hasn't logged in in a while
* ``token_id`` (external ID) Only set on users' profiles if you have admin permissions.

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

You can also fetch multiple profiles at once::

    => ["user.fetch", 123, {"ids": ["1234", "5679"]}]
    <- ["success", 123, {"1234": {"id": "1234", "profile": {…}}, "5679": {…}}]

If one of the user does not exist, it will not be part of the response, but there will be no error message.
The maximum number of users that can be fetched in one go is 100.

Instead of IDs, you can also pass a set of ``pretalx_id`` values::

    => ["user.fetch", 123, {"pretalx_ids": ["DKJ2E", "24"]}]
    <- ["success", 123, {"DKJ2E": {"id": "1234", "pretalx_id": "DKJ2E", "profile": {…}}, "5679": {…}}]

Profile updates
---------------

If your user data changes, you will receive a broadcast with your new profile. This is e.g. important if your profile
is changed from a different connection::

    <= ["user.updated", {"id": "1234", "profile": {…}}]

Fetching a list of users
------------------------

If you have sufficient permissions, you can fetch a list of all users like this::

    => ["user.list", 123, {"ids": ["1234", "5679"]}]
    <- ["success", 123, {"1234": {"id": "1234", "profile": {…}}, "5679": {…}}]

.. note:: Pagination will be implemented on this endpoint in the future.

Searching users
---------------

You can search all users to get a 1-based paginated list like this::

    => ["user.list.search", 123, {"search_term": "", "badge": null, "page": 1}]
    <- ["success", 123, {"results": [{"id": "1234", "profile": {…}}, "5679": {…}], "isLastPage": true}]

The size of the pages can be configured in the world config with ``user_list.page_size``. The default is 20.
An empty list will be returned if ``search_term`` is shorter than ``user_list.search_min_chars``.
If ``user_list.search_min_chars`` is set to 0, which is also the default, an empty search term will return a paginated
list of all users.
If you set ``badge``, only users with that badge will be retunred.
Invalid page numbers return an empty list.
If there are no more results to be fetched the ``isLastPage`` will be set to true.

Managing users
--------------

With sufficient permissions, you can ban or silence a user. A banned user will be locked out from the system completely,
a silenced user can still read everything but cannot join video calls and cannot send chat messages.

To ban a user, send::

    => ["user.ban", 123, {"id": "1234"}]
    <- ["success", 123, {}]

To silence a user, send::

    => ["user.silence", 123, {"id": "1234"}]
    <- ["success", 123, {}]

Trying to silence a banned user will be ignored.

To fully reinstantiate either a banned or silenced user, send::

    => ["user.reactivate", 123, {"id": "1234"}]
    <- ["success", 123, {}]

Blocking users
--------------

Everyone can block other users. Blocking currently means the other users cannot start new direct messages to you. If
they already have an open direct message channel with you, they cannot send any new messages to that channel.

To block a user, send::

    => ["user.block", 123, {"id": "1234"}]
    <- ["success", 123, {}]

To unblock a user, send::

    => ["user.unblock", 123, {"id": "1234"}]
    <- ["success", 123, {}]

To get a list of blocked users, send::

    => ["user.list.blocked", 123, {}]
    <- ["success", 123, [{"id": "1234", "profile": {…}}]]
