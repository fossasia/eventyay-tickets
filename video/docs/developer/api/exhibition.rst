Exhibition module
====================

Message flow
------------

To get a short list of all exhibitors in a room, a client can push a message like this::

    => ["exhibition.list", 1234, {"room": "room_1"}]
    <- ["success", 1234, {"exhibitors": []}]

The response will contain a shortened list with the fields

* ``id``: (string)
* ``name``: (string)
* ``tagline``: (string)
* ``logo``: (string, image url)
* ``short_text``: (string)
* ``size``: (string, "1x1", "3x1" or "3x3)
* ``sorting_priority``: (integer)

To get comprehensive profile of an exhibitor, a client can push a message like this::

    => ["exhibition.get", 1234, {"exhibitor": "exhibitor_id"}]
    <- ["success", 1234, {"exhibitor": {...}]

The response will contain the fields

* ``name``: (string)
* ``tagline``: (string)
* ``logo``: (string, image url)
* ``banner_list``: (string, image url)
* ``banner_detail``: (string, image url)
* ``contact_enabled``: (boolean)
* ``text``: (string, markdown)
* ``size``: (string, "1x1", "3x1" or "3x3)
* ``sorting_priority``: (integer)
* ``links``: (list of objects ``{"url", "display_text"}``)
* ``social_media_links``: (list of objects ``{"url", "display_text"}``)
* ``staff``: (list of user objects)

Contact request
---------------

To request a private chat with one of the staff members of an exhibitor, a client can push a message like this::

    => ["exhibition.contact", 1234, {"exhibitor": id}]
    <- ["success", 1234, {}]

A contact request (with state "open") will be send to all clients associated as staff::

    <- ["exhibition.contact_request", {id, exhibitor_id, user_id, state}]

A client can accept the contact request with a message like this::

    => ["exhibition.contact_accept", 1234, {"contact_request": id}]
    <- ["success", 1234, {}]

The client which requested the contact will be send a message like::

    <- ["exhibition.contact_accepted", {"contact_request": {id, exhibitor, user, state}, "channel": "…"}]

The state will become "answered" and messages send to all staff members::

    <- ["exhibition.contact_request_close", {"contact_request": {id, exhibitor, user, state}}]

Cancel contact request
----------------------

A client can cancel a contact request with a message like this::

    => ["exhibition.contact_cancel", 1234, {"contact_request": id}]
    <- ["success", 1234, {}]

The state will be set to "missed" and messages send to all staff members::

    <- ["exhibition.contact_request_close", {"contact_request": {id, exhibitor, user, state}}]

