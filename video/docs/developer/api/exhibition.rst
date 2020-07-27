Exhibition module
====================

Message flow
------------

To get a short list of all exhibitors in a room, a client can push a message like this::

    => ["exhibition.list", 1234, {"room": "room_1"}]
    <- ["success", 1234, {"exhibitors": []}]

The response will contain a shortened list with the fields
* ``id`` (string)
* ``name`` (string)
* ``tagline`` (string)
* ``logo`` (string, image url)
* ``short_text`` (string)
* ``size`` (string, "1x1", "3x1" or "3x3)
* ``sorting_priority`` (integer)

To get comprehensive profile of an exhibitor, a client can push a message like this::

    => ["exhibition.get", 1234, {"exhibitor": "exhibitor_id"}]
    <- ["success", 1234, {"exhibitor": {...}]

The response will contain the fields
* ``name`` (string)
* ``tagline`` (string)
* ``logo`` (string, image url)
* ``text`` (string, markdown)
* ``size`` (string, "1x1", "3x1" or "3x3)
* ``sorting_priority`` (integer)
* ``links`` (list of objects ``{"url", "display_text"}``)
* ``social_media_links`` (list of objects ``{"url", "display_text"}``)
* ``staff`` (list of user IDs)
