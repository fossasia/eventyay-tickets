Poster module
=============

Room view API
-------------

To get a list of all posters in a room, a client can push a message like this::

    => ["poster.list", 1234, {"room": "room_1"}]
    <- ["success", 1234, [{…}]]

To get a list of all posters in a room, a client can push a message like this::

    => ["poster.get.presented_by_user", 1234, {"user_id": "user_234"}]
    <- ["success", 1234, [{…}]]

To get a single entry, a client can push a message like this::

    => ["poster.get", 1234, {"poster": "poster_id"}]
    <- ["success", 1234, {...}]

The response in all cases will contain a list with the fields:

* ``id``: (string)
* ``title``: (string)
* ``abstract``: (string)
* ``authors``: TODO
* ``category``: (string)
* ``tags``: (list of strings)
* ``poster_url``: (string, asset url)
* ``poster_preview``: (string, image url)
* ``schedule_session``: (string)
* ``presenters``: (list of user objects)
* ``votes``: (integer)
* ``links``: (list of objects)

  * ``display_text`` (string)
  * ``url`` (string)
  * ``sorting_priority`` (integer)

* ``parent_room_id``: (string, room uuid)
* ``channel``: (string, channel uuid)
* ``presentation_room_id``: (string, image url)
* ``has_voted``: (boolean)

To vote or unvote for an entry, a client can push a message like this::

    => ["poster.vote", 1234, {"poster": "poster_id"}]
    <- ["success", 1234, {}]

    => ["poster.unvote", 1234, {"poster": "poster_id"}]
    <- ["success", 1234, {}]


Management API
--------------

To get a list of all posters a user can manage, a client can push a message like this::

    => ["poster.list.all", 1234, {}]
    <- ["success", 1234, [{…}]]

To delete a poster, you can send::

    => ["poster.delete", 1234, {"poster": "poster_id"}]
    <- ["success", 1234, [{…}]]

To update a poster, you can send::

    => ["poster.patch", 1234, {"id": "poster_id", "category": "Science"}]
    <- ["success", 1234, [{…}]]

To create a new poster, send ``poster.patch`` with the ``id`` field set to ``""``.