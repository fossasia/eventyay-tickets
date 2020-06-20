World
=====

Resource description
--------------------

The world resource contains the following public fields:

.. rst-class:: rest-resource-table

===================================== ========================== =======================================================
Field                                 Type                       Description
===================================== ========================== =======================================================
id                                    string                     The world's ID
title                                 string                     A title for the world
config                                object                     Various configuration properties
permission_config                     object                     Permission rules mapping permission keys to lists of
                                                                 traits
domain                                string                     The FQDN of this world
===================================== ========================== =======================================================

Endpoints
---------

.. http:get:: /api/v1/worlds/(world_id)/

   Returns the representation of the selected world.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/worlds/sample/ HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      {
        "id": "sample",
        "title": "Unsere tolle Online-Konferenz",
        "config": {},
        "permission_config": {
            "world.update": ["admin"],
            "world.secrets": ["admin", "api"],
            "world.announce": ["admin"],
            "world.api": ["admin", "api"],
            "room.create": ["admin"],
            "room.announce": ["admin"],
            "room.update": ["admin"],
            "room.delete": ["admin"],
            "chat.moderate": ["admin"],
        },
        "domain": "sample.venueless.events"
      }

   :statuscode 200: no error
   :statuscode 401: Authentication failure
   :statuscode 403: The world does not exist **or** you have no permission to view it.

.. http:patch:: /api/v1/worlds/(world_id)/

   Updates a world

   **Example request**:

   .. sourcecode:: http

      PATCH /api/v1/worlds/sample/ HTTP/1.1
      Accept: application/json, text/javascript
      Content-Type: application/json

      {
        "title": "Happy World"
      }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      {
        "id": "sample",
        "title": "Happy World",
        "config": {},
        "permission_config": {
            "world.update": ["admin"],
            "world.secrets": ["admin", "api"],
            "world.announce": ["admin"],
            "world.api": ["admin", "api"],
            "room.create": ["admin"],
            "room.announce": ["admin"],
            "room.update": ["admin"],
            "room.delete": ["admin"],
            "chat.moderate": ["admin"],
        },
        "domain": "sample.venueless.events"
      }

   :statuscode 200: no error
   :statuscode 400: The world could not be updated due to invalid submitted data.
   :statuscode 401: Authentication failure
   :statuscode 403: The requested organizer/event does not exist **or** you have no permission to create this resource.
