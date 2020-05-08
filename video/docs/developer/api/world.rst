World configuration
===================

The world configuration is pushed to the client first as part of the successful authentication response.
If the world config changes, you will get an update like this::

    <= ["world.update", { … }]

The body of the configuration is structured like this, filtered to user visibility:


.. code-block:: json

    {
        "world": {
            "title": "Unsere tolle Online-Konferenz",
            "permissions": []
        },
        "rooms": [
            {
                "id": "room_1",
                "name": "Plenum",
                "description": "Hier findet die Eröffnungs- und End-Veranstaltung statt",
                "picture": "https://via.placeholder.com/150",
                "permissions": [],
                "modules": [
                    {
                        "type": "livestream.native",
                        "config": {
                            "hls_url": "https://s1.live.pretix.eu/test/index.m3u8"
                        },
                        "permissions": []
                    },
                    {
                        "type": "chat.native",
                        "config": {
                        },
                        "permissions": []
                    },
                    {
                        "type": "agenda.pretalx",
                        "config": {
                            "api_url": "https://pretalx.com/conf/online/schedule/export/schedule.json",
                            "room_id": 3
                        },
                        "permissions": []
                    }
                ]
            },
            {
                "id": "room_2",
                "name": "Gruppenraum 1",
                "description": "Hier findet die Eröffnungs- und End-Veranstaltung statt",
                "picture": "https://via.placeholder.com/150",
                "permissions": [],
                "access": [
                    {
                        "level": "viewer",
                        "permissions": []
                    },
                    {
                        "level": "moderator",
                        "permissions": []
                    }
                ],
                "modules": [
                    {
                        "type": "call.bigbluebutton",
                        "config": {},
                        "permissions": []
                    }
                ]
            }
        ]
    }


Permissions
-----------

Permissions are rendered **to the user** as a list of strings. This list contains agreed permission names, with the
default attendee requiring not permissions at all (an empty list). Permissions agreed so far include:

- ``world.update``
- ``world.announce``
- ``room.create``
- ``room.update``
- ``room.delete``
- ``chat.create``
- ``chat.update``
- ``chat.delete``
- ``chat.moderate``


On the **configuration** side of things, permissions are a dictionary, mapping from a permission to the required traits
a token needs to have, like this:

.. code-block:: json

    {
        "permissions": {
            "world.update": ["trait1", "trait2"],
            "room.update": ["trait2"],
        }
    }
