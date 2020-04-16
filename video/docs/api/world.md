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
            ]
        },
        "rooms": [
            {
                "id": "room_1",
                "name": "Plenum",
                "description": "Hier findet die Eröffnungs- und End-Veranstaltung statt",
                "picture": "https://via.placeholder.com/150",
                "access": [
                    {
                        "level": "viewer",
                        "required_traits": []
                    },
                    {
                        "level": "moderator",
                        "required_traits": ["moderator_plenum"]
                    }
                ],
                "modules": [
                    {
                        "type": "livestream.native",
                        "config": {
                            "hls_url": "https://s1.live.pretix.eu/test/index.m3u8"
                        }
                    },
                    {
                        "type": "chat.native",
                        "config": {
                        }
                    },
                    {
                        "type": "agenda.pretalx",
                        "config": {
                            "api_url": "https://pretalx.com/conf/online/schedule/export/schedule.json",
                            "room_id": 3
                        }
                    }
                ]
            },
            {
                "id": "room_2",
                "name": "Gruppenraum 1",
                "description": "Hier findet die Eröffnungs- und End-Veranstaltung statt",
                "picture": "https://via.placeholder.com/150",
                "access": [
                    {
                        "level": "viewer",
                        "required_traits": []
                    },
                    {
                        "level": "moderator",
                        "required_traits": ["moderator_plenum"]
                    }
                ],
                "modules": [
                    {
                        "type": "call.bigbluebutton",
                        "config": {
                            "bbb_join_url": "https://s1.live.pretix.eu/test/index.m3u8"
                        }
                    }
                ]
            }
        ]
    }
