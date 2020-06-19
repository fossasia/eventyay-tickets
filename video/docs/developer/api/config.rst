.. _world-config:

World configuration
===================

The world configuration is pushed to the client first as part of the successful authentication response.
If the world config changes, you will get an update like this::

    <= ["world.update", { … }]

The body of the configuration is structured like this, filtered to user visibility:
The first room acts as the landing page.

.. code-block:: json

    {
        "world": {
            "title": "Unsere tolle Online-Konferenz",
            "permissions": ["world:view"]
        },
        "rooms": [
            {
                "id": "room_1",
                "name": "Plenum",
                "description": "Hier findet die Eröffnungs- und End-Veranstaltung statt",
                "picture": "https://via.placeholder.com/150",
                "permissions": ["room:view", "room:chat.read"],
                "modules": [
                    {
                        "type": "livestream.native",
                        "config": {
                            "hls_url": "https://s1.live.pretix.eu/test/index.m3u8"
                        },
                    },
                    {
                        "type": "chat.native",
                        "config": {
                        },
                    },
                    {
                        "type": "agenda.pretalx",
                        "config": {
                            "api_url": "https://pretalx.com/conf/online/schedule/export/schedule.json",
                            "room_id": 3
                        },
                    }
                ]
            },
            {
                "id": "room_2",
                "name": "Gruppenraum 1",
                "description": "Hier findet die Eröffnungs- und End-Veranstaltung statt",
                "picture": "https://via.placeholder.com/150",
                "permissions": ["room:view"],
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
