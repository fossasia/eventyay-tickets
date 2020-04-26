World configuration
===================

The world configuration is pushed directly after authentication with a message structured as

    <- ["world.config", { … }]
    
The body of the configuration is strucured like this, filtered to user visibility:

    {
        "world": {
            "title": "Unsere tolle Online-Konferenz",
            "JWT_secrets": [
                {
                    "issuer": "pretix.eu",
                    "audience": "audience",
                    "secret": "secret"
                }
            ],
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
                        "required_traits": [],
                        "permissions": []
                    },
                    {
                        "level": "moderator",
                        "required_traits": ["moderator_plenum"],
                        "permissions": []
                    }
                ],
                "modules": [
                    {
                        "type": "call.bigbluebutton",
                        "config": {
                            "bbb_join_url": "https://s1.live.pretix.eu/test/index.m3u8"
                        },
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

- `world.update`
- `world.announce`
- `room.create`
- `room.update`
- `room.delete`
- `chat.create`
- `chat.update`
- `chat.delete`
- `chat.moderate`


On the **configuration** side of things, permissions are a dictionary, mapping from a permission to the required traits
a token needs to have, like this:

```json
{
    "permissions": {
        "world.update": ["trait1", "trait2"],
        "room.update": ["trait2"],
    },
}
```
